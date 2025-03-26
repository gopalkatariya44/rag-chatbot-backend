from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List

from app.core.crypto import encrypt_key, decrypt_key
from app.db.models import User, UserModelPreference, UserAPIKey
from app.models.users import UserOut


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str):
        result = await self.db.execute(select(User).filter(User.email == email))
        return result.scalars().first()

    async def create_user(self, email: str, hashed_password: str):
        new_user = User(email=email, hashed_password=hashed_password)
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def set_model_preferences(self, user_id: UUID, provider: str, embedding_model: str, chat_model: str):
        # Fetch the user with model_preferences eagerly loaded
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.model_preferences))  # Eagerly load model_preferences
            .filter(User.id == user_id)
        )
        user = result.scalars().first()

        if not user:
            raise ValueError("User not found")

        # If the user doesn't have model_preferences, create a new one
        if not user.model_preferences:
            user.model_preferences = UserModelPreference()

        # Update the preferences
        user.model_preferences.provider = provider
        user.model_preferences.embedding_model = embedding_model
        user.model_preferences.chat_model = chat_model

        # Commit the changes
        await self.db.commit()
        await self.db.refresh(user.model_preferences)

        return user.model_preferences

    async def add_api_key(self, user_id: UUID, provider: str, api_key: str):
        encrypted_key = encrypt_key(api_key)
        new_api_key = UserAPIKey(user_id=user_id, provider=provider, encrypted_key=encrypted_key)
        self.db.add(new_api_key)
        await self.db.commit()
        await self.db.refresh(new_api_key)
        return new_api_key

    async def get_api_key(self, user_id: UUID, provider: str):
        result = await self.db.execute(
            select(UserAPIKey).filter(UserAPIKey.user_id == user_id, UserAPIKey.provider == provider)
        )
        api_key = result.scalars().first()
        if api_key:
            return decrypt_key(api_key.encrypted_key)
        return None

    async def delete_api_key(self, user_id: UUID, provider: str) -> bool:
        """Delete an API key for a user and provider"""
        try:
            # First find the key
            result = await self.db.execute(
                select(UserAPIKey).filter(
                    UserAPIKey.user_id == user_id,
                    UserAPIKey.provider == provider
                )
            )
            api_key = result.scalars().first()
            
            if api_key:
                # Delete the key
                await self.db.delete(api_key)
                await self.db.commit()
                print(f"Successfully deleted API key for provider {provider}")
                return True
            
            print(f"No API key found for provider {provider}")
            return False
            
        except Exception as e:
            print(f"Error deleting API key: {str(e)}")
            await self.db.rollback()
            raise

    async def get_user_with_preferences(self, user_id: UUID) -> Optional[User]:
        """Get user with model preferences"""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.model_preferences))
            .filter(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_api_keys(self, user_id: UUID) -> List[UserAPIKey]:
        """Get all API keys for a user"""
        result = await self.db.execute(
            select(UserAPIKey).filter(UserAPIKey.user_id == user_id)
        )
        api_keys = result.scalars().all()
        
        # Decrypt the keys before returning
        for key in api_keys:
            key.encrypted_key = decrypt_key(key.encrypted_key)
        
        return api_keys
