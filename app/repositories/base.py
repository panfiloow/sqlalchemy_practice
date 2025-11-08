from typing import Any, Dict, List, Optional, Generic, TypeVar
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db_session: AsyncSession):
        self.model = model
        self.db_session = db_session

    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        result = await self.db_session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ModelType]:
        result = await self.db_session.execute(
            select(self.model)
            .offset(skip)
            .limit(limit)
            .order_by(self.model.id)
        )
        return result.scalars().all()

    async def create(self, obj_in: Dict[str, Any]) -> ModelType:
        db_obj = self.model(**obj_in)
        self.db_session.add(db_obj)
        await self.db_session.commit()
        await self.db_session.refresh(db_obj)
        return db_obj

    async def update(
        self, 
        db_obj: ModelType, 
        obj_in: Dict[str, Any]
    ) -> ModelType:
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        await self.db_session.commit()
        await self.db_session.refresh(db_obj)
        return db_obj

    async def delete(self, id: Any) -> bool:
        result = await self.db_session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.db_session.commit()
        return result.rowcount > 0

    async def count(self) -> int:
        result = await self.db_session.execute(
            select(func.count(self.model.id))
        )
        return result.scalar_one()