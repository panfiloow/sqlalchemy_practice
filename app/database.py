from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

class Base(DeclarativeBase):
    pass

# Для Alembic используем sync engine
def get_database_url():
    """Получает URL базы данных для Alembic (синхронный)"""
    async_url = settings.DATABASE_URL
    # Конвертируем асинхронный URL в синхронный для Alembic
    if async_url.startswith('sqlite+aiosqlite'):
        return async_url.replace('sqlite+aiosqlite', 'sqlite')
    elif async_url.startswith('postgresql+asyncpg'):
        return async_url.replace('postgresql+asyncpg', 'postgresql')
    return async_url

# Асинхронный engine для приложения
engine = create_async_engine(settings.DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_async_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()