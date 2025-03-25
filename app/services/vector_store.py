from typing import Union
from uuid import UUID
from langchain_community.vectorstores.pgvector import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.models.users import UserOut
from app.core.security import get_api_key_for_provider
from app.db.repositories.users import UserRepository

async def get_embedding_function(user: UserOut, api_key: str):
    """Get the appropriate embedding function based on user preferences"""
    if user.model_preferences.provider == "openai":
        return OpenAIEmbeddings(
            model=user.model_preferences.embedding_model,
            api_key=api_key
        )
    elif user.model_preferences.provider == "google":
        return GoogleGenerativeAIEmbeddings(
            model=user.model_preferences.embedding_model,
            google_api_key=api_key,
            task_type="retrieval_query"
        )
    else:
        raise ValueError(f"Unsupported provider for embeddings: {user.model_preferences.provider}")

async def get_vector_store(db: AsyncSession, user_id: Union[str, UUID]) -> PGVector:
    """Get vector store based on user preferences"""
    try:
        # Convert user_id to UUID if it's a string
        if isinstance(user_id, str):
            user_id = UUID(user_id)
            
        # Get user with preferences
        user_repo = UserRepository(db)
        user = await user_repo.get_user_with_preferences(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        # Get API key for the provider
        api_key = await get_api_key_for_provider(user.id, user.model_preferences.provider, db)
        
        # Get embedding function
        embedding_function = await get_embedding_function(user, api_key)

        connection_string = str(settings.DATABASE_URL)
        if connection_string.startswith('postgresql+asyncpg://'):
            connection_string = connection_string.replace('postgresql+asyncpg://', 'postgresql://')

        collection_name = str(user.id)  # Use just the UUID as collection name
        
        # Debug: Check vectors in database
        result = await db.execute(
            text("""
                SELECT COUNT(*) 
                FROM langchain_pg_embedding 
                WHERE cmetadata->>'user_id' = :user_id
            """),
            {
                "user_id": str(user_id)
            }
        )
        count = result.scalar()
        print(f"Found {count} vectors for user {user_id}")
        
        # Create vector store
        vector_store = PGVector(
            connection_string=connection_string,
            embedding_function=embedding_function,
            collection_name=collection_name,  # Just use the UUID
            distance_strategy="cosine"
        )
        
        return vector_store
    except Exception as e:
        print(f"Error getting vector store: {str(e)}")
        print(f"Full error details: {str(e.__class__.__name__)}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise 