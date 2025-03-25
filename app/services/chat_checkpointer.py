from typing import Any, Dict, Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ChatState  # Update import path
import json

class PostgresChatCheckpointer:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load state from database"""
        result = await self.db.execute(
            select(ChatState).filter(ChatState.session_id == session_id)
        )
        state = result.scalar_one_or_none()
        return state.state if state else None
        
    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """Save state to database"""
        chat_state = ChatState(
            session_id=session_id,
            state={
                "current_input": state["current_input"],
                "internal_history": state["internal_history"],
                "current_output": state["current_output"],
                "current_context": state["current_context"],
                "session_id": state["session_id"],
                "retriever_params": state["retriever_params"],
                "conversation_count": state["conversation_count"],
                "user_id": state["user_id"]
            }
        )
        await self.db.merge(chat_state)
        await self.db.commit()

async def load_chat_state(session_id: str, db: AsyncSession) -> Dict[str, Any]:
    """Load chat state from database"""
    try:
        result = await db.execute(
            text("SELECT state FROM chat_states WHERE session_id = :session_id"),
            {"session_id": session_id}
        )
        row = result.fetchone()
        if not row:
            return None
        return json.loads(row[0])
    except Exception as e:
        print(f"Error loading chat state: {str(e)}")
        raise

async def save_chat_state(state: Dict[str, Any], db: AsyncSession):
    """Save chat state to database"""
    try:
        await db.execute(
            text("""
                INSERT INTO chat_states (session_id, state)
                VALUES (:session_id, :state::jsonb)
                ON CONFLICT (session_id) 
                DO UPDATE SET state = :state::jsonb
            """),
            {
                "session_id": state["session_id"],
                "state": json.dumps(state)
            }
        )
        await db.commit()
    except Exception as e:
        print(f"Error saving chat state: {str(e)}")
        await db.rollback()
        raise 