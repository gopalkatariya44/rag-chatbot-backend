import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.sql import text
from sqlalchemy.schema import Index

from app.db.session import Base


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

    model_preferences = relationship("UserModelPreference", back_populates="user", uselist=False, lazy="selectin")
    api_keys = relationship("UserAPIKey", back_populates="user")
    documents = relationship("Document", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    status = Column(String, default="pending")
    file_path = Column(String)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    chunks = relationship("DocumentChunk", back_populates="document")
    user = relationship("User", back_populates="documents")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    chunk_text = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(JSONB)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))

    document = relationship("Document", back_populates="chunks")


class UserModelPreference(Base):
    __tablename__ = "user_model_preferences"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    provider = Column(String, nullable=False)  # e.g., "openai", "google"
    embedding_model = Column(String, default="text-embedding-3-small")  # Default to OpenAI
    chat_model = Column(String, default="gpt-4")  # Default to GPT-4
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="model_preferences")


class UserAPIKey(Base):
    __tablename__ = "user_api_keys"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    provider = Column(String, nullable=False)  # e.g., "openai", "google"
    encrypted_key = Column(String, nullable=False)  # Encrypted API key
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")

    @property
    def decrypted_key(self):
        """
        Decrypt the API key using the crypto utility.
        """
        from app.core.crypto import decrypt_key
        return decrypt_key(self.encrypted_key)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # "human" or "ai"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


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

    # Add index on the user_id in the JSON state
    __table_args__ = (
        Index('ix_chat_states_user_id', 
              text("((state->>'user_id')::text)"),
              postgresql_using='btree'
        ),
    )
