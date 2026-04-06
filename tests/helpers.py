from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

def make_fake_redis(**overrides) -> MagicMock:
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=0)
    mock.exists = AsyncMock(return_value=False)
    mock.expire = AsyncMock(return_value=True)
    mock.incr = AsyncMock(return_value=1)
    mock.scard = AsyncMock(return_value=0)
    mock.smembers = AsyncMock(return_value=set())
    mock.mget = AsyncMock(return_value=[None, None, None])
    mock.pipeline = MagicMock()
    for k, v in overrides.items():
        setattr(mock, k, v)
    return mock

def make_fake_pipe(**overrides) -> MagicMock:
    pipe = MagicMock()
    pipe.set = MagicMock()
    pipe.get = MagicMock()
    pipe.delete = MagicMock()
    pipe.sadd = MagicMock()
    pipe.srem = MagicMock()
    pipe.expire = MagicMock()
    pipe.zadd = MagicMock()
    pipe.zrem = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    for k, v in overrides.items():
        setattr(pipe, k, v)
    return pipe

class MockAsyncClient:
    def __init__(self, *, response=None, error=None):
        self._response = response
        self._error = error

    async def __aenter__(self):
        if self._error:
            raise self._error
        return self._response or MagicMock()

    async def __aexit__(self, exc_type, exc, tb):
        return False

class MockMessage:
    def __init__(self, body: dict, headers: dict | None = None, retry_count: int = 0):
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

SAMPLE_DT = datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)

def make_booking_data(**overrides) -> dict:
    base = {
        "user_email": "user@example.com",
        "handyman_email": "handyman@example.com",
        "desired_start": SAMPLE_DT,
        "desired_end": SAMPLE_DT + timedelta(hours=2),
        "job_description": "Fix leaky faucet",
    }
    base.update(overrides)
    return base

def make_event(**overrides) -> dict:
    base = {
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
    base.update(overrides)
    return base

def make_handyman(**overrides) -> dict:
    base = {
        "email": "pro@example.com",
        "skills": ["plumbing"],
        "years_experience": 5,
        "service_radius_km": 20,
        "latitude": 45.001,
        "longitude": 9.001,
        "avg_rating": 4.5,
        "rating_count": 10,
        "profile_completeness": 80,
        "completed_jobs_count": 5,
    }
    base.update(overrides)
    return base

def make_intervals() -> dict:
    base = datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)
    return {
        "interval_a": (base, base + timedelta(hours=2)),
        "interval_b": (base + timedelta(hours=1), base + timedelta(hours=3)),
        "interval_c": (base + timedelta(hours=4), base + timedelta(hours=5)),
        "interval_d": (base, base + timedelta(hours=1)),
    }