from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as redis_async

from tests.service_loader import load_service_app_module


@pytest.fixture
def reservations_module(monkeypatch):
    fake_redis = MagicMock()
    fake_redis.smembers = AsyncMock(return_value=set())
    fake_redis.get = AsyncMock(return_value=None)
    fake_redis.pipeline = MagicMock()

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis_async, "from_url", lambda *args, **kwargs: fake_redis)

    load_service_app_module(
        "availability-service",
        "redis_client",
        package_name="availability_service_test_app",
        reload_modules=True,
    )
    module = load_service_app_module(
        "availability-service",
        "reservations",
        package_name="availability_service_test_app",
    )
    module.redis_client = fake_redis
    return module


@pytest.mark.unit
class TestReservationKeys:

    def test_res_key(self, reservations_module):
        assert reservations_module._res_key("booking-1") == "reservation:booking-1"

    def test_res_handyman_set(self, reservations_module):
        assert reservations_module._res_handyman_set("pro@example.com") == "reservations_by_handyman:pro@example.com"


@pytest.mark.unit
class TestReservationCrud:

    @pytest.mark.asyncio
    async def test_create_reservation_persists_payload(self, reservations_module, monkeypatch):
        fake_pipe = MagicMock()
        fake_pipe.set = MagicMock()
        fake_pipe.sadd = MagicMock()
        fake_pipe.expire = MagicMock()
        fake_pipe.zadd = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[True, 1, True, 1])
        reservations_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)
        monkeypatch.setattr(reservations_module.time, "time", lambda: 1000.0)

        result = await reservations_module.create_reservation(
            "booking-1",
            "pro@example.com",
            "2026-03-17T10:00:00+00:00",
            "2026-03-17T12:00:00+00:00",
        )

        assert result is True
        payload_json = fake_pipe.set.call_args.args[1]
        payload = json.loads(payload_json)
        assert payload["booking_id"] == "booking-1"
        assert payload["handyman_email"] == "pro@example.com"
        fake_pipe.expire.assert_called_once_with("reservations_by_handyman:pro@example.com", reservations_module.RES_TTL_SECONDS + 30)
        fake_pipe.zadd.assert_called_once_with("reservation_expiry", {"booking-1": 1000.0 + reservations_module.RES_TTL_SECONDS})

    @pytest.mark.asyncio
    async def test_create_reservation_rejects_overlap(self, reservations_module):
        reservations_module.redis_client.smembers = AsyncMock(return_value={"booking-existing"})
        reservations_module.redis_client.get = AsyncMock(
            return_value=json.dumps(
                {
                    "desired_start": "2026-03-17T10:00:00+00:00",
                    "desired_end": "2026-03-17T12:00:00+00:00",
                }
            )
        )

        result = await reservations_module.create_reservation(
            "booking-new",
            "pro@example.com",
            "2026-03-17T11:00:00+00:00",
            "2026-03-17T13:00:00+00:00",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_create_reservation_skips_invalid_existing_payloads(self, reservations_module):
        fake_pipe = MagicMock()
        fake_pipe.set = MagicMock()
        fake_pipe.sadd = MagicMock()
        fake_pipe.expire = MagicMock()
        fake_pipe.zadd = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[True, 1, True, 1])
        reservations_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)
        reservations_module.redis_client.smembers = AsyncMock(return_value={"bad-1", "bad-2"})
        reservations_module.redis_client.get = AsyncMock(side_effect=["not-json", None])

        result = await reservations_module.create_reservation(
            "booking-new",
            "pro@example.com",
            "2026-03-17T13:00:00+00:00",
            "2026-03-17T14:00:00+00:00",
        )

        assert result is True
        fake_pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_reservation_returns_none_when_missing(self, reservations_module):
        reservations_module.redis_client.get = AsyncMock(return_value=None)

        result = await reservations_module.get_reservation("booking-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_reservation_returns_none_for_bad_json(self, reservations_module):
        reservations_module.redis_client.get = AsyncMock(return_value="not-json")

        result = await reservations_module.get_reservation("booking-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_reservation_returns_payload(self, reservations_module):
        reservations_module.redis_client.get = AsyncMock(return_value='{"booking_id":"booking-1"}')

        result = await reservations_module.get_reservation("booking-1")

        assert result == {"booking_id": "booking-1"}

    @pytest.mark.asyncio
    async def test_delete_reservation_removes_handyman_mapping(self, reservations_module):
        fake_pipe = MagicMock()
        fake_pipe.delete = MagicMock()
        fake_pipe.zrem = MagicMock()
        fake_pipe.srem = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[1, 1, 1])
        reservations_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)
        reservations_module.get_reservation = AsyncMock(
            return_value={"handyman_email": "pro@example.com"}
        )

        await reservations_module.delete_reservation("booking-1")

        fake_pipe.delete.assert_called_once_with("reservation:booking-1")
        fake_pipe.zrem.assert_called_once_with("reservation_expiry", "booking-1")
        fake_pipe.srem.assert_called_once_with("reservations_by_handyman:pro@example.com", "booking-1")

    @pytest.mark.asyncio
    async def test_delete_reservation_handles_missing_reservation(self, reservations_module):
        fake_pipe = MagicMock()
        fake_pipe.delete = MagicMock()
        fake_pipe.zrem = MagicMock()
        fake_pipe.srem = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[1, 1])
        reservations_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)
        reservations_module.get_reservation = AsyncMock(return_value=None)

        await reservations_module.delete_reservation("booking-1")

        fake_pipe.delete.assert_called_once_with("reservation:booking-1")
        fake_pipe.zrem.assert_called_once_with("reservation_expiry", "booking-1")
        fake_pipe.srem.assert_not_called()