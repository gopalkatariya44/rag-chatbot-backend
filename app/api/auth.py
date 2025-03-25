from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password, create_access_token, get_current_user
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.models.users import UserCreate, UserOut

router = APIRouter(tags=["Auth"])


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


@router.post("/api-keys")
async def add_api_key(
        provider: str,
        api_key: str,
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
    await user_repo.add_api_key(current_user.id, provider, api_key)
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


@router.put("/model-preferences")
async def set_model_preferences(
        provider: str,  # Add provider as a parameter
        embedding_model: str,
        chat_model: str,
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
            current_user.id, provider, embedding_model, chat_model
        )
        return preferences
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
