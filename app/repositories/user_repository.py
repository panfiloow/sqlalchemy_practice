from typing import Optional
from sqlalchemy import select
from app.models.user import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, db_session):
        super().__init__(User, db_session)

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db_session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db_session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username_or_email(
        self, 
        username: str, 
        email: str
    ) -> Optional[User]:
        result = await self.db_session.execute(
            select(User).where(
                (User.username == username) | (User.email == email)
            )
        )
        return result.scalar_one_or_none()