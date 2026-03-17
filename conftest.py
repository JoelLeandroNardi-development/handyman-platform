import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_mock():
    mock = AsyncMock()
    mock.set = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock(return_value=0)
    mock.exists = AsyncMock(return_value=False)
    mock.expire = AsyncMock(return_value=True)
    return mock


@pytest.fixture
async def rabbit_channel_mock():
    mock = AsyncMock()
    mock.set_qos = AsyncMock()
    mock.declare_exchange = AsyncMock()
    mock.declare_queue = AsyncMock()
    mock.get_queue = AsyncMock()
    return mock


@pytest.fixture
async def rabbit_message_mock():
    mock = AsyncMock()
    mock.body = json.dumps({"test": "payload"}).encode("utf-8")
    mock.headers = {}
    mock.content_type = "application/json"
    mock.ack = AsyncMock()
    mock.reject = AsyncMock()
    mock.nack = AsyncMock()
    return mock


@pytest.fixture
def sample_datetime():
    return datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_booking_data(sample_datetime):
    return {
        "user_email": "user@example.com",
        "handyman_email": "handyman@example.com",
        "desired_start": sample_datetime,
        "desired_end": sample_datetime + timedelta(hours=2),
        "job_description": "Fix leaky faucet",
    }


@pytest.fixture
def sample_event():
    return {
        "event_type": "booking.requested",
        "aggregate_id": "booking-123",
        "data": {
            "booking_id": "booking-123",
            "user_email": "user@example.com",
            "handyman_email": "handyman@example.com",
            "desired_start": "2026-03-17T10:00:00+00:00",
            "desired_end": "2026-03-17T12:00:00+00:00",
            "job_description": "Fix leaky faucet",
        },
        "timestamp": "2026-03-17T10:00:00+00:00",
    }


@pytest.fixture
def sample_intervals():
    base = datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)
    return {
        "interval_a": (base, base + timedelta(hours=2)),
        "interval_b": (base + timedelta(hours=1), base + timedelta(hours=3)),
        "interval_c": (base + timedelta(hours=4), base + timedelta(hours=5)),
        "interval_d": (base, base + timedelta(hours=1)),
    }


@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        from sqlalchemy import MetaData
        pass
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    yield async_session
    
    async with engine.begin() as conn:
        await conn.run_sync(lambda conn: None)
    
    await engine.dispose()


class MockMessage:
    
    def __init__(self, body: dict, headers: dict = None, retry_count: int = 0):
        self.body = json.dumps(body).encode("utf-8")
        self.headers = headers or {}
        self.headers["x-retry-count"] = retry_count
        self.content_type = "application/json"
        self.ack_called = False
        self.reject_called = False
        self.reject_requeue = False
        self.nack_called = False
    
    async def ack(self):
        self.ack_called = True
    
    async def reject(self, requeue: bool = False):
        self.reject_called = True
        self.reject_requeue = requeue
    
    async def nack(self, requeue: bool = False):
        self.nack_called = True


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_redis():
    return MagicMock()

