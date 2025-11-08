from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.user import User
from app.core.security import decode_access_token
from app.config import settings
from app.repositories.user_repository import UserRepository

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    token = request.cookies.get(settings.COOKIE_ACCESS_NAME)
    if not token:
        raise credentials_exception
    
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
            
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    return current_user

# Dependency for services
async def get_auth_service(db: AsyncSession = Depends(get_async_session)):
    from app.services.auth_service import AuthService
    return AuthService(db)

async def get_user_service(db: AsyncSession = Depends(get_async_session)):
    from app.services.user_service import UserService
    return UserService(db)