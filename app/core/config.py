from pydantic_settings import BaseSettings
from pydantic import validator, EmailStr
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Chatbot"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: str
    SECRET_KEY: str
    FERNET_SECRET_KEY: str
    
    # Security
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: list[str] = [
        "text/plain",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]

    DATABASE_LOGS: bool = False

    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must be PostgreSQL")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
