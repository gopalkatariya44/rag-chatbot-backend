from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import datetime

from app.core.security import get_password_hash, verify_password, create_access_token, get_current_user
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.models.users import UserCreate, UserOut

router = APIRouter(tags=["Auth"])

# Add these new models
class ModelPreferences(BaseModel):
    provider: str
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None

class APIKeys(BaseModel):
    openai: Optional[str] = None
    google: Optional[str] = None

class APIKeyResponse(BaseModel):
    provider: str
    key: str
    created_at: datetime

@router.post("/register", response_model=UserOut)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        user_repo = UserRepository(db)
        existing_user = await user_repo.get_by_email(user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        hashed_password = get_password_hash(user.password)
        new_user = await user_repo.create_user(email=user.email, hashed_password=hashed_password)
        return new_user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

class APIKeyRequest(BaseModel):
    provider: str
    api_key: str

@router.post("/api-keys")
async def add_api_key(
        request: APIKeyRequest,
        db: AsyncSession = Depends(get_db),
        current_user: UserOut = Depends(get_current_user),
):
    """
    Add an API key for a provider
    Args:
        provider: The provider to add the API key to
        api_key: The API key to add
    Returns:
        A message indicating that the API key was added successfully
    
    Example:
     - provider: google
     - api_key: 1234567890
    
    Resource:
     - https://aistudio.google.com/apikey
    """
    user_repo = UserRepository(db)
    await user_repo.add_api_key(current_user.id, request.provider, request.api_key)
    return {"detail": "API key added successfully"}


@router.delete("/api-keys/{provider}")
async def delete_api_key(
        provider: str,
        db: AsyncSession = Depends(get_db),
        current_user: UserOut = Depends(get_current_user),
):
    """
    Delete an API key for a provider
    Args:
        provider: The provider to delete the API key from
    Returns:
        A message indicating that the API key was deleted successfully
    
    Example:
     - provider: google
    """
    user_repo = UserRepository(db)
    deleted = await user_repo.delete_api_key(current_user.id, provider)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No API key found for provider: {provider}",
        )
    return {"detail": "API key deleted successfully"}

class ModelPreferencesRequest(BaseModel):
    provider: str
    embedding_model: str
    chat_model: str


@router.put("/model-preferences")
async def set_model_preferences(
        request: ModelPreferencesRequest,
        db: AsyncSession = Depends(get_db),
        current_user: UserOut = Depends(get_current_user),
):
    """
    Set model preferences for a user
    Args:
        provider: The provider to set the model preferences for
        embedding_model: The embedding model to set
        chat_model: The chat model to set
    Returns:
        A message indicating that the model preferences were set successfully
    
    Example:
     - provider: google
     - embedding_model: models/embedding-001
     - chat_model: models/gemini-1.5-pro-002
    """
    user_repo = UserRepository(db)
    try:
        preferences = await user_repo.set_model_preferences(
            current_user.id, request.provider, request.embedding_model, request.chat_model
        )
        return preferences
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def get_api_keys(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of saved API keys for the current user
    
    Returns:
        List of API keys with their providers and creation dates
    """
    try:
        user_repo = UserRepository(db)
        api_keys = await user_repo.get_all_api_keys(current_user.id)
        
        return [
            APIKeyResponse(
                provider=key.provider,
                key=key.encrypted_key,  # This will be decrypted by the repository
                created_at=key.created_at
            )
            for key in api_keys
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving API keys: {str(e)}"
        )

@router.get("/model-preferences", response_model=ModelPreferences)
async def get_preferences(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get model preferences for the current user
    
    Returns:
        ModelPreferences containing provider and model settings
    """
    try:
        user_repo = UserRepository(db)
        user = await user_repo.get_user_with_preferences(current_user.id)
        
        if not user or not user.model_preferences:
            return ModelPreferences(
                provider="openai",  # Default provider
                embedding_model="text-embedding-3-small",  # Default embedding model
                chat_model="gpt-3.5-turbo"  # Default chat model
            )
            
        return ModelPreferences(
            provider=user.model_preferences.provider,
            embedding_model=user.model_preferences.embedding_model,
            chat_model=user.model_preferences.chat_model
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving model preferences: {str(e)}"
        )
