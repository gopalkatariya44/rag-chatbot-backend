from sqlalchemy import Column, String, JSON, DateTime, func
from app.db.session import Base

class ChatState(Base):
    __tablename__ = "chat_states"

    session_id = Column(String, primary_key=True)
    state = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    ) 