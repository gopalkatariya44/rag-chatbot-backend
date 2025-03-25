from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.security import get_api_key_for_provider
from app.db.models import UserModelPreference


async def generate_embeddings(texts: list[str], provider: str, embedding_model: str, api_key: str) -> list[list[float]]:
    if provider == "openai":
        embeddings = OpenAIEmbeddings(model=embedding_model, openai_api_key=api_key)
    elif provider == "google":
        embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model, google_api_key=api_key)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    return await embeddings.aembed_documents(texts)


async def get_embeddings_model(user_id: UUID, provider: str, db: AsyncSession):
    """Get embeddings model based on user preferences"""
    api_key = await get_api_key_for_provider(user_id, provider, db)
    
    result = await db.execute(
        select(UserModelPreference).filter(UserModelPreference.user_id == user_id)
    )
    preferences = result.scalars().first()
    
    if not preferences:
        raise ValueError("User model preferences not found")
    
    if provider == "openai":
        return OpenAIEmbeddings(
            api_key=api_key,
            model=preferences.embedding_model  # Use as-is for OpenAI
        )
    elif provider == "google":
        return GoogleGenerativeAIEmbeddings(
            api_key=api_key,
            model=preferences.embedding_model  # Use as-is for Google
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")
