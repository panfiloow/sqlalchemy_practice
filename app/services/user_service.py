from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repository import UserRepository
from app.schemas.user import UsersListResponse

class UserService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.user_repo = UserRepository(db_session)

    async def create_user(self, username: str, email: str, password: str):
        from app.core.security import hash_password
        
        # Check if user exists
        existing_user = await self.user_repo.get_by_username_or_email(username, email)
        if existing_user:
            from fastapi import HTTPException, status
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

    async def get_users_paginated(self, page: int, size: int) -> UsersListResponse:
        offset = (page - 1) * size
        
        total = await self.user_repo.count()
        users = await self.user_repo.get_all(offset, size)
        
        pages = (total + size - 1) // size
        
        return UsersListResponse(
            items=users,
            total=total,
            page=page,
            size=size,
            pages=pages
        )

    async def get_user_by_id(self, user_id: str):
        return await self.user_repo.get_by_id(user_id)

    async def get_user_by_username(self, username: str):
        return await self.user_repo.get_by_username(username)