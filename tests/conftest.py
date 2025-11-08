import pytest

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models.models import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def engine():
    # Создаем engine с in-memory SQLite для тестов
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Создаем все таблицы
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def session(engine):
    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
async def client(session):
    # Переопределяем зависимость базы данных
    async def override_get_db():
        yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Создаем тестового клиента
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    # Очищаем переопределения после теста
    app.dependency_overrides.clear()

# Фикстура для тестовых данных
@pytest.fixture
async def test_user(session):
    user = User(email="test@example.com", username="testuser")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user