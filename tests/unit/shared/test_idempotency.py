from unittest.mock import AsyncMock

import pytest

from shared.core.utils.idempotency import (
    already_processed,
    IDEMPOTENCY_DEFAULT_TTL_SECONDS,
)

@pytest.mark.unit
@pytest.mark.idempotency
class TestAlreadyProcessed:
    @pytest.mark.asyncio
    async def test_first_occurrence_returns_false(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)

        assert await already_processed(redis_client=redis_mock, event_id="evt-1") is False

        redis_mock.set.assert_called_once_with(
            "processed_event:evt-1", "1",
            ex=IDEMPOTENCY_DEFAULT_TTL_SECONDS, nx=True,
        )

    @pytest.mark.asyncio
    async def test_duplicate_returns_true(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=False)

        assert await already_processed(redis_client=redis_mock, event_id="evt-1") is True

    @pytest.mark.asyncio
    async def test_custom_ttl(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)

        await already_processed(redis_client=redis_mock, event_id="evt-1", ttl_seconds=7200)

        redis_mock.set.assert_called_once_with(
            "processed_event:evt-1", "1", ex=7200, nx=True,
        )

    @pytest.mark.asyncio
    async def test_custom_prefix(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)

        await already_processed(redis_client=redis_mock, event_id="evt-1", prefix="my_events")

        assert redis_mock.set.call_args[0][0] == "my_events:evt-1"

    @pytest.mark.asyncio
    async def test_custom_prefix_and_ttl(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)

        await already_processed(
            redis_client=redis_mock,
            event_id="booking-456",
            ttl_seconds=3600,
            prefix="booking_events",
        )

        redis_mock.set.assert_called_once_with(
            "booking_events:booking-456", "1", ex=3600, nx=True,
        )

    @pytest.mark.asyncio
    async def test_value_is_string_one(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)

        await already_processed(redis_client=redis_mock, event_id="evt-1")

        value = redis_mock.set.call_args[0][1]
        assert value == "1" and isinstance(value, str)

    def test_default_ttl_constant(self):
        assert IDEMPOTENCY_DEFAULT_TTL_SECONDS == 3600

@pytest.mark.unit
@pytest.mark.idempotency
class TestIdempotencyFlow:

    @pytest.mark.asyncio
    async def test_process_then_replay(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)
        assert await already_processed(redis_client=redis_mock, event_id="evt-1") is False

        redis_mock.set = AsyncMock(return_value=False)
        assert await already_processed(redis_client=redis_mock, event_id="evt-1") is True

    @pytest.mark.asyncio
    async def test_expired_event_can_reprocess(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)
        assert await already_processed(redis_client=redis_mock, event_id="evt-1", ttl_seconds=1) is False

        redis_mock.set = AsyncMock(return_value=True)
        assert await already_processed(redis_client=redis_mock, event_id="evt-1", ttl_seconds=1) is False