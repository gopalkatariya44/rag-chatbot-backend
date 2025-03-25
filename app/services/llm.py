from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import select

from app.core.security import get_api_key_for_provider
from app.db.models import UserModelPreference

async def get_chat_model(user_id: UUID, provider: str, db: AsyncSession):
    """Get chat model based on user preferences"""
    # Get API key
    api_key = await get_api_key_for_provider(user_id, provider, db)
    
    # Get user's model preferences
    result = await db.execute(
        select(UserModelPreference).filter(UserModelPreference.user_id == user_id)
    )
    preferences = result.scalars().first()
    
    if not preferences:
        raise ValueError("User model preferences not found")
    
    if provider == "openai":
        return ChatOpenAI(
            api_key=api_key,
            model=preferences.chat_model  # Use model name as-is for OpenAI
        )
    elif provider == "google":
        # Only add "models/" prefix for Google models if not already present
        model_name = preferences.chat_model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
            
        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model_name,
            convert_system_message_to_human=True
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}") 