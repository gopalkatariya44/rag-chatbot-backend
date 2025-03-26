from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List
from datetime import datetime
from uuid import UUID

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.users import UserOut
from app.db.models import ChatSession, ChatMessage

router = APIRouter(tags=["Chat Sessions"])

class ChatSessionResponse(BaseModel):
    """Response model for chat session"""
    session_id: str
    last_message: str
    conversation_count: int
    created_at: datetime
    updated_at: datetime | None = None

# Add this model for chat messages
class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    """
    List all chat sessions for the current user
    
    Returns:
        List of chat sessions with their details
    """
    try:
        # Query chat sessions with message counts and last message
        query = select(
            ChatSession,
            func.count(ChatMessage.id).label('message_count'),
            func.max(ChatMessage.created_at).label('last_message_time'),
            func.max(ChatMessage.content).label('last_content')
        ).outerjoin(
            ChatMessage, ChatSession.id == ChatMessage.session_id
        ).filter(
            ChatSession.user_id == current_user.id
        ).group_by(
            ChatSession.id
        ).order_by(
            ChatSession.created_at.desc()
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            ChatSessionResponse(
                session_id=str(row.ChatSession.id),
                last_message=row.last_content or "",
                conversation_count=row.message_count,
                created_at=row.ChatSession.created_at,
                updated_at=row.last_message_time
            )
            for row in rows
        ]
        
    except Exception as e:
        print(f"Error listing chat sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chat sessions"
        )

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_session_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    """
    Get all messages for a specific chat session
    
    Args:
        session_id: UUID of the chat session
        
    Returns:
        List of messages in chronological order
    """
    try:
        # First verify the session belongs to the user
        session_result = await db.execute(
            select(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            )
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
            
        # Get all messages for the session
        messages_result = await db.execute(
            select(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = messages_result.scalars().all()
        
        return [
            ChatMessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at
            )
            for msg in messages
        ]
        
    except Exception as e:
        print(f"Error getting session messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chat messages"
        )
