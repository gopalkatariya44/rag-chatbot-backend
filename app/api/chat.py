from typing import Optional, List, Dict, Any
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.users import UserOut
from app.services.chat_flow import ChatFlow
from app.services.chat_checkpointer import PostgresChatCheckpointer
from app.core.security import get_api_key_for_provider

router = APIRouter(tags=["Chat"])

class ChatInput(BaseModel):
    session_id: Optional[str] = Field(default=None, examples=[None])
    message: str = Field(examples=["What is Yolo?"])

class DocumentContext(BaseModel):
    """Model for document context"""
    content: str
    source: str
    score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    session_id: str
    response: str
    conversation_count: int
    context: List[DocumentContext] = Field(
        default=[],
        description="List of relevant document chunks used to answer the question"
    )

@router.post("/chat", response_model=ChatResponse)
async def chat(
    input: ChatInput,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    """Chat endpoint that handles both new and existing sessions"""
    try:
        # Check if user has model preferences configured
        if not current_user.model_preferences:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please configure your model preferences first"
            )
            
        # Validate provider
        provider = current_user.model_preferences.provider
        valid_providers = ["google", "openai"]  # Add supported providers here
        if provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}. Supported providers are: {', '.join(valid_providers)}"
            )
            
        # Check for API key
        try:
            await get_api_key_for_provider(current_user.id, provider, db)
        except HTTPException as e:
            if "No API key found" in str(e.detail):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Please add your {provider} API key in settings before chatting"
                )
            raise e

        print(f"\n=== Starting Chat Request ===")
        print(f"Message: {input.message}")
        print(f"Session ID: {input.session_id}")
        print(f"User ID: {current_user.id}")
        print(f"Provider: {provider}")
        
        chat_flow = ChatFlow(db, str(current_user.id))
        checkpointer = PostgresChatCheckpointer(db)
        
        session_id = input.session_id
        if not session_id:
            # Create new session
            session_id = str(uuid4())
            print(f"Creating new chat session: {session_id}")
            state = chat_flow.get_initial_state(session_id)
        else:
            # Load existing session
            print(f"Loading existing chat session: {session_id}")
            state = await checkpointer.load(session_id)
            if not state:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chat session {session_id} not found"
                )
            # Verify session belongs to user
            if state["user_id"] != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this chat session"
                )

        print(f"Initial state: {state}")
        
        # Update state with new message
        state["current_input"] = input.message
        
        # Process message
        try:
            state = await chat_flow.process(state)
            print(f"Processed state: {state}")
            
            # Convert document context to response format
            context = []
            if state.get("current_context"):
                for doc in state["current_context"]:
                    context.append(DocumentContext(
                        content=doc["page_content"],
                        source=doc["metadata"].get("source", "unknown"),
                        score=doc["metadata"].get("score"),
                        metadata=doc["metadata"]
                    ))
            
        except Exception as e:
            print(f"Error in chat_flow.process: {str(e)}")
            import traceback
            traceback.print_exc()
            state["current_output"] = "Sorry, I encountered an error. Please make sure your API key and model preferences are correctly configured."
            state["conversation_count"] = 0
            context = []
        
        # Save updated state
        try:
            await checkpointer.save(session_id, state)
            print("State saved successfully")
        except Exception as e:
            print(f"Error saving state: {str(e)}")
            raise
        
        return ChatResponse(
            response=state["current_output"],
            session_id=session_id,
            conversation_count=state["conversation_count"],
            context=context
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
