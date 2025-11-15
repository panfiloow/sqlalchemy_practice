from datetime import datetime, timedelta
from typing import Optional, Tuple
import secrets
from jose import JWTError, jwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    verify_password, 
    create_access_token, 
    hash_password,
    decode_refresh_token
)
from app.repositories.user_repository import UserRepository
from app.repositories.token_repository import TokenRepository
from app.models.user import User
from app.config import settings

#TODO: OAUTH2
class AuthService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.user_repo = UserRepository(db_session)
        self.token_repo = TokenRepository(db_session)

    async def authenticate_user(
        self, 
        username: str, 
        password: str
    ) -> Optional[User]:
        user = await self.user_repo.get_by_username(username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def register_user(
        self, 
        username: str, 
        email: str, 
        password: str
    ) -> User:
        # Check if user exists
        existing_user = await self.user_repo.get_by_username_or_email(
            username, email
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email or username already exists"
            )
        
        # Create user
        user_data = {
            "username": username,
            "email": email,
            "hashed_password": hash_password(password)
        }
        return await self.user_repo.create(user_data)

    async def create_tokens(self, user_id: str) -> Tuple[str, str]:
        """Create both access and refresh tokens"""
        access_token = create_access_token({"sub": str(user_id)})
        refresh_token = await self._create_and_save_refresh_token(str(user_id))
        
        return access_token, refresh_token

    async def _create_and_save_refresh_token(self, user_id: str) -> str:
        """Create refresh token and save to database"""
        token_jti = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Create refresh token JWT
        refresh_token = jwt.encode(
            {
                "sub": user_id,
                "type": "refresh",
                "jti": token_jti,
                "exp": expires_at
            },
            settings.REFRESH_SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        # Save to database
        token_data = {
            "user_id": user_id,
            "token_jti": token_jti,
            "expires_at": expires_at
        }
        await self.token_repo.create(token_data)
        
        return refresh_token

    async def refresh_tokens(
        self, 
        refresh_token: str
    ) -> Tuple[str, str]:
        """Refresh access token using refresh token"""
        try:
            # Verify refresh token
            payload = decode_refresh_token(refresh_token)
            
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Not a refresh token")
                
            user_id = payload.get("sub")
            token_jti = payload.get("jti")
            
            if not user_id or not token_jti:
                raise HTTPException(status_code=401, detail="Invalid token payload")
            
            # Check if token exists in database and is valid
            db_token = await self.token_repo.get_by_jti(token_jti)
            if not db_token:
                raise HTTPException(status_code=401, detail="Token revoked")
            
            # Check if token is expired
            if datetime.utcnow() > db_token.expires_at:
                await self.token_repo.revoke_by_jti(token_jti)
                raise HTTPException(status_code=401, detail="Token expired")
            
            # Revoke old token
            await self.token_repo.revoke_by_jti(token_jti)
            
            # Create new tokens
            new_access_token = create_access_token({"sub": user_id})
            new_refresh_token = await self._create_and_save_refresh_token(user_id)
            
            return new_access_token, new_refresh_token
            
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    async def logout(self, refresh_token_jti: str) -> bool:
        """Revoke specific refresh token"""
        return await self.token_repo.revoke_by_jti(refresh_token_jti) > 0

    async def logout_all(self, user_id: str) -> int:
        """Revoke all user's refresh tokens"""
        return await self.token_repo.revoke_by_user_id(user_id)

    async def verify_refresh_token(self, request) -> User:
        """Verify refresh token and return user"""
    
        refresh_token = request.cookies.get(settings.COOKIE_REFRESH_NAME)
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Refresh token not found")
        
        try:
            payload = decode_refresh_token(refresh_token)
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Not a refresh token")
                
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="No user ID in token")
                
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid refresh token: {str(e)}")
        
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
