from typing import List, Optional, TypedDict, Union, Any, Dict
from langchain_core.messages import AIMessage, BaseMessage as AnyMessage, HumanMessage
from langchain_core.documents import Document
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import UserModelPreference
from app.services.vector_store import get_vector_store
from app.services.llm import get_chat_model
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import select

class ChatState(TypedDict):
    current_input: str
    internal_history: list
    current_output: str | None
    current_context: list | None
    session_id: str
    retriever_params: dict
    conversation_count: int
    user_id: str

class ChatFlow:
    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        
    def _serialize_message(self, message: AnyMessage) -> Dict[str, str]:
        """Serialize a message to dict"""
        return {
            "type": message.__class__.__name__,
            "content": message.content
        }

    def _deserialize_message(self, message_dict: Dict[str, str]) -> AnyMessage:
        """Deserialize a message from dict"""
        if message_dict["type"] == "HumanMessage":
            return HumanMessage(content=message_dict["content"])
        return AIMessage(content=message_dict["content"])

    def _serialize_document(self, doc: Document) -> Dict[str, Any]:
        """Serialize a document to dict"""
        return {
            "page_content": doc.page_content,
            "metadata": doc.metadata
        }

    def _deserialize_document(self, doc_dict: Dict[str, Any]) -> Document:
        """Deserialize a document from dict"""
        return Document(
            page_content=doc_dict["page_content"],
            metadata=doc_dict["metadata"]
        )

    async def _filter_documents(self, state: ChatState) -> ChatState:
        """Filter and retrieve relevant documents"""
        try:
            # Rollback any failed transaction
            await self.db.rollback()
            
            print(f"Filtering documents for input: {state['current_input']}")
            
            # Debug: Check documents in database first
            result = await self.db.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM langchain_pg_embedding 
                    WHERE cmetadata->>'user_id' = :user_id
                """),
                {"user_id": state["user_id"]}
            )
            chunk_count = result.scalar()
            print(f"Found {chunk_count} chunks for user in vector store")

            # Check if there are any documents
            if chunk_count == 0:
                print("No documents found in vector store")
                state["current_context"] = []
                return state

            try:
                vector_store = await get_vector_store(self.db, state["user_id"])
                
                # Configure retriever with better search parameters
                retriever = vector_store.as_retriever(
                    search_type="similarity",
                    search_kwargs={
                        "k": 5,
                        "where": {
                            "cmetadata": {
                                "user_id": str(state["user_id"])
                            }
                        }
                    }
                )
                
                query = state["current_input"]
                print(f"\nSearching with query: {query}")
                
                try:
                    docs = await retriever.aget_relevant_documents(query)
                    print(f"Retrieved {len(docs)} documents")
                    
                    # Convert documents to serializable format
                    state["current_context"] = [
                        {
                            "page_content": doc.page_content,
                            "metadata": doc.metadata
                        }
                        for doc in docs
                    ]
                    
                except Exception as e:
                    if "different vector dimensions" in str(e):
                        print("Vector dimension mismatch - provider change detected")
                        # Clear existing embeddings for this user
                        await self.db.execute(
                            text("""
                                DELETE FROM langchain_pg_embedding 
                                WHERE cmetadata->>'user_id' = :user_id
                            """),
                            {"user_id": state["user_id"]}
                        )
                        await self.db.commit()
                        
                        state["current_context"] = []
                        state["current_output"] = (
                            "I noticed you changed your AI provider. Please re-upload your documents "
                            "to create new embeddings compatible with the current provider."
                        )
                        return state
                    else:
                        raise e

            except Exception as e:
                print(f"Error getting vector store: {str(e)}")
                print(f"Full error details: {e}")
                raise

            return state
            
        except Exception as e:
            print(f"Database error in filter_documents: {str(e)}")
            await self.db.rollback()
            raise

    async def _answer_with_rag(self, state: ChatState) -> ChatState:
        """Generate answer using RAG"""
        try:
            # Rollback any failed transaction
            await self.db.rollback()
            
            # Get user's model preferences from state
            result = await self.db.execute(
                select(UserModelPreference).filter(UserModelPreference.user_id == self.user_id)
            )
            preferences = result.scalars().first()
            if not preferences:
                raise ValueError("User model preferences not found")
            
            # Use the provider from user preferences
            llm = await get_chat_model(state["user_id"], preferences.provider, self.db)
            
            docs = [self._deserialize_document(doc) for doc in (state["current_context"] or [])]
            context_str = "\n\n".join([doc.page_content for doc in docs])
            print(f"Using context of length: {len(context_str)}")
            print(f"First 200 chars of context: {context_str[:200]}...")
            
            history = [self._deserialize_message(msg) for msg in state["internal_history"]]
            print(f"Chat history length: {len(history)}")
            
            prompt = f"""Context: {context_str}

Question: {state["current_input"]}

Please answer the question based on the provided context. If the answer cannot be found in the context, say so. Include relevant quotes from the context to support your answer."""

            messages = [
                AIMessage(content="I am a helpful AI assistant that provides accurate answers based on the given context."),
                *history,
                HumanMessage(content=prompt)
            ]
            
            print("Sending request to LLM...")
            response = await llm.ainvoke(messages)
            print(f"LLM Response: {response.content}")
            
            state["current_output"] = response.content
            state["conversation_count"] += 1
            
            state["internal_history"].extend([
                self._serialize_message(HumanMessage(content=state["current_input"])),
                self._serialize_message(AIMessage(content=response.content))
            ])
            
            # Commit the transaction
            await self.db.commit()
            return state
            
        except SQLAlchemyError as e:
            print(f"Database error in answer_with_rag: {str(e)}")
            await self.db.rollback()
            raise
        except Exception as e:
            print(f"Error in answer_with_rag: {str(e)}")
            await self.db.rollback()
            state["current_output"] = "I apologize, but I encountered an error processing your request."
            return state

    async def process(self, state: ChatState) -> ChatState:
        """Process the chat flow"""
        try:
            print("\n=== Processing Chat Flow ===")
            print(f"Input: {state['current_input']}")
            
            # Start fresh transaction
            await self.db.rollback()
            
            try:
                state = await self._filter_documents(state)
                print("Documents filtered successfully")
            except Exception as e:
                print(f"Error in _filter_documents: {str(e)}")
                raise
            
            try:
                state = await self._answer_with_rag(state)
                print("Answer generated successfully")
            except Exception as e:
                print(f"Error in _answer_with_rag: {str(e)}")
                raise
            
            await self.db.commit()
            return state
            
        except Exception as e:
            print(f"Error in process: {str(e)}")
            await self.db.rollback()
            import traceback
            traceback.print_exc()
            raise

    def get_initial_state(self, session_id: str) -> ChatState:
        """Get initial state for a chat session"""
        return ChatState(
            current_input="",
            internal_history=[],
            current_output=None,
            current_context=None,
            session_id=session_id,
            retriever_params={"k": 4, "score_threshold": 0.5},
            conversation_count=0,
            user_id=self.user_id
        ) 