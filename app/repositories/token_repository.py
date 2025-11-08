from typing import List, Optional
from sqlalchemy import delete, select
from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository

class TokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, db_session):
        super().__init__(RefreshToken, db_session)

    async def get_by_jti(self, token_jti: str) -> Optional[RefreshToken]:
        result = await self.db_session.execute(
            select(RefreshToken).where(RefreshToken.token_jti == token_jti)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> List[RefreshToken]:
        result = await self.db_session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        return result.scalars().all()

    async def revoke_by_user_id(self, user_id: str) -> int:
        result = await self.db_session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        await self.db_session.commit()
        return result.rowcount

    async def revoke_by_jti(self, token_jti: str) -> int:
        result = await self.db_session.execute(
            delete(RefreshToken).where(RefreshToken.token_jti == token_jti)
        )
        await self.db_session.commit()
        return result.rowcount