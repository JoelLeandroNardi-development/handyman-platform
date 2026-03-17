import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


@pytest.fixture
async def test_db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        pass
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
async def fake_redis():
    try:
        from fakeredis.aioredis import FakeRedis
        return FakeRedis()
    except ImportError:
        pytest.skip("fakeredis not installed")


@pytest.fixture
def mock_rabbit_publisher():
    from unittest.mock import AsyncMock, MagicMock
    
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    publisher.close = AsyncMock()
    return publisher

