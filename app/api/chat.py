from typing import Optional, List, Dict, Any
from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, get_api_key_for_provider
from app.db.models import ChatSession, ChatMessage
from app.db.session import get_db
from app.models.users import UserOut
from app.services.chat_flow import ChatFlow
from app.services.chat_checkpointer import PostgresChatCheckpointer

router = APIRouter(tags=["Chat"])

class ChatInput(BaseModel):
    """Input model for chat endpoint"""
    session_id: Optional[str] = Field(default=None, description="Session ID for continuing a conversation")
    message: str = Field(..., description="User's message", examples=["What is YOLO?"])

class DocumentContext(BaseModel):
    """Model for document context"""
    content: str = Field(..., description="Content of the document chunk")
    source: str = Field(..., description="Source of the document")
    score: Optional[float] = Field(None, description="Relevance score")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    session_id: str = Field(..., description="ID of the chat session")
    response: str = Field(..., description="AI's response")
    conversation_count: int = Field(..., description="Number of messages in conversation")
    context: List[DocumentContext] = Field(
        default=[],
        description="List of relevant document chunks used to answer the question"
    )

@router.post("/chat", response_model=ChatResponse)
async def chat(
    input: ChatInput,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
) -> ChatResponse:
    """
    Chat endpoint that handles both new and existing sessions
    
    Args:
        input: Chat input containing message and optional session_id
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        ChatResponse containing AI's response and context
        
    Raises:
        HTTPException: If user setup is incomplete or session is invalid
    """
    try:
        # Validate user setup
        if not current_user.model_preferences:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please configure your model preferences first"
            )
            
        # Validate provider
        provider = current_user.model_preferences.provider
        valid_providers = ["google", "openai"]
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

        # Initialize services
        chat_flow = ChatFlow(db, str(current_user.id))
        checkpointer = PostgresChatCheckpointer(db)
        
        # Get or create session state
        session_id = input.session_id
        if not session_id:
            # Generate new session ID
            session_id = str(uuid4())
            state = chat_flow.get_initial_state(session_id)
            
            # Create new chat session in database
            new_session = ChatSession(
                id=UUID(session_id),
                user_id=current_user.id
            )
            db.add(new_session)
            # Commit the session immediately to avoid foreign key issues
            await db.commit()
        else:
            state = await checkpointer.load(session_id)
            if not state:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chat session {session_id} not found"
                )
            if state["user_id"] != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this chat session"
                )

        try:
            # Save user message
            user_message = ChatMessage(
                session_id=UUID(session_id),
                role="human",
                content=input.message
            )
            db.add(user_message)
            await db.commit()  # Commit user message

            # Process message
            state["current_input"] = input.message
            state = await chat_flow.process(state)
            
            # Save AI response
            ai_message = ChatMessage(
                session_id=UUID(session_id),
                role="ai",
                content=state["current_output"]
            )
            db.add(ai_message)
            await db.commit()  # Commit AI message

            context = [
                DocumentContext(
                    content=doc["page_content"],
                    source=doc["metadata"].get("source", "unknown"),
                    score=doc["metadata"].get("score"),
                    metadata=doc["metadata"]
                )
                for doc in (state.get("current_context") or [])
            ]

            # Save state
            await checkpointer.save(session_id, state)
            
            return ChatResponse(
                response=state["current_output"],
                session_id=session_id,
                conversation_count=state["conversation_count"],
                context=context
            )

        except Exception as e:
            await db.rollback()
            print(f"Error processing chat: {str(e)}")
            raise

    except Exception as e:
        await db.rollback()
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
