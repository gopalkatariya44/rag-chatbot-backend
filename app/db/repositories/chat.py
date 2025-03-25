from datetime import datetime
from typing import Optional, List
from uuid import UUID

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession, ChatMessage
from app.db.repositories.base import BaseRepository

class AsyncChatMessageHistory(BaseChatMessageHistory):
    """Async implementation of chat message history"""
    
    def __init__(self, session_id: str, chat_repo: 'ChatRepository'):
        self.session_id = session_id
        self.chat_repo = chat_repo
        self.messages: List[BaseMessage] = []
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the chat history (sync)"""
        self.messages.append(message)
    
    def clear(self) -> None:
        """Clear the chat history (sync)"""
        self.messages = []
    
    def get_messages(self) -> List[BaseMessage]:
        """Get messages from the chat history (sync)"""
        return self.messages
        
    async def aget_messages(self) -> List[BaseMessage]:
        """Get messages from the chat history (async)"""
        return await self.chat_repo.get_chat_history(UUID(self.session_id))
    
    async def aappend(self, message: BaseMessage) -> None:
        """Append a message to the chat history (async)"""
        # Note: We handle message saving separately in save_chat_history
        self.add_message(message)
    
    async def aclear(self) -> None:
        """Clear the chat history (async)"""
        await self.chat_repo.clear_chat_history(UUID(self.session_id))
        self.clear()

class ChatRepository(BaseRepository):
    async def get_or_create_session(self, session_id: UUID, user_id: UUID) -> ChatSession:
        """Get or create a chat session"""
        result = await self.db.execute(
            select(ChatSession).filter(ChatSession.id == session_id)
        )
        session = result.scalars().first()
        
        if not session:
            session = ChatSession(id=session_id, user_id=user_id)
            self.db.add(session)
            await self.db.commit()
        
        return session

    async def get_chat_history(self, session_id: UUID) -> List[BaseMessage]:
        """Get chat history for a session"""
        result = await self.db.execute(
            select(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        
        return [
            HumanMessage(content=msg.content) if msg.role == "human"
            else AIMessage(content=msg.content)
            for msg in messages
        ]

    async def save_chat_history(
        self, 
        session_id: UUID, 
        human_message: HumanMessage, 
        ai_message: AIMessage
    ) -> None:
        """Save messages to chat history"""
        # Save human message
        human_msg = ChatMessage(
            session_id=session_id,
            role="human",
            content=human_message.content
        )
        self.db.add(human_msg)
        
        # Save AI message
        ai_msg = ChatMessage(
            session_id=session_id,
            role="ai",
            content=ai_message.content
        )
        self.db.add(ai_msg)
        
        await self.db.commit()

    async def clear_chat_history(self, session_id: UUID) -> None:
        """Clear chat history for a session"""
        await self.db.execute(
            select(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        )
        await self.db.commit()

    def get_message_history(self, session_id: str) -> AsyncChatMessageHistory:
        """Get message history for LangChain"""
        return AsyncChatMessageHistory(session_id, self)
