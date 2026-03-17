from unittest.mock import AsyncMock

import pytest

from shared.shared.idempotency import (
    already_processed,
    IDEMPOTENCY_DEFAULT_TTL_SECONDS,
)


@pytest.mark.unit
@pytest.mark.idempotency
class TestAlreadyProcessed:

    @pytest.mark.asyncio
    async def test_first_occurrence_not_processed(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)
        
        result = await already_processed(
            redis_client=redis_mock,
            event_id="event-123",
        )
        
        assert result is False
        redis_mock.set.assert_called_once_with(
            "processed_event:event-123",
            "1",
            ex=IDEMPOTENCY_DEFAULT_TTL_SECONDS,
            nx=True,
        )
    
    @pytest.mark.asyncio
    async def test_duplicate_occurrence_already_processed(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=False)
        
        result = await already_processed(
            redis_client=redis_mock,
            event_id="event-123",
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_custom_ttl(self, redis_mock):
        custom_ttl = 7200
        redis_mock.set = AsyncMock(return_value=True)
        
        await already_processed(
            redis_client=redis_mock,
            event_id="event-123",
            ttl_seconds=custom_ttl,
        )
        
        redis_mock.set.assert_called_once_with(
            "processed_event:event-123",
            "1",
            ex=custom_ttl,
            nx=True,
        )
    
    @pytest.mark.asyncio
    async def test_custom_prefix(self, redis_mock):
        custom_prefix = "my_events"
        redis_mock.set = AsyncMock(return_value=True)
        
        await already_processed(
            redis_client=redis_mock,
            event_id="event-123",
            prefix=custom_prefix,
        )
        
        redis_mock.set.assert_called_once_with(
            "my_events:event-123",
            "1",
            ex=IDEMPOTENCY_DEFAULT_TTL_SECONDS,
            nx=True,
        )
    
    @pytest.mark.asyncio
    async def test_custom_ttl_and_prefix(self, redis_mock):
        custom_ttl = 3600
        custom_prefix = "booking_events"
        redis_mock.set = AsyncMock(return_value=True)
        
        await already_processed(
            redis_client=redis_mock,
            event_id="booking-456",
            ttl_seconds=custom_ttl,
            prefix=custom_prefix,
        )
        
        redis_mock.set.assert_called_once_with(
            "booking_events:booking-456",
            "1",
            ex=custom_ttl,
            nx=True,
        )
    
    @pytest.mark.asyncio
    async def test_multiple_different_events(self, redis_mock):
        redis_mock.set = AsyncMock(side_effect=[True, False])
        
        result1 = await already_processed(
            redis_client=redis_mock,
            event_id="event-123",
        )
        assert result1 is False
        
        result2 = await already_processed(
            redis_client=redis_mock,
            event_id="event-456",
        )
        assert result2 is True
        
        assert redis_mock.set.call_count == 2
        calls = redis_mock.set.call_args_list
        assert "event-123" in calls[0][0][0]
        assert "event-456" in calls[1][0][0]
    
    @pytest.mark.asyncio
    async def test_default_ttl_constant(self):
        assert IDEMPOTENCY_DEFAULT_TTL_SECONDS == 3600
    
    @pytest.mark.asyncio
    async def test_key_format(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)
        
        event_id = "uuid-12345"
        prefix = "test_prefix"
        
        await already_processed(
            redis_client=redis_mock,
            event_id=event_id,
            prefix=prefix,
        )
        
        call_args = redis_mock.set.call_args
        key = call_args[0][0]
        assert key == f"{prefix}:{event_id}"
    
    @pytest.mark.asyncio
    async def test_value_always_one_string(self, redis_mock):
        redis_mock.set = AsyncMock(return_value=True)
        
        await already_processed(
            redis_client=redis_mock,
            event_id="event-123",
        )
        
        call_args = redis_mock.set.call_args
        value = call_args[0][1]
        assert value == "1"
        assert isinstance(value, str)


@pytest.mark.unit
@pytest.mark.idempotency
class TestIdempotencyIntegration:

    @pytest.mark.asyncio
    async def test_event_processing_idempotency_flow(self, redis_mock):
        event_id = "booking-requested-789"
        
        redis_mock.set = AsyncMock(return_value=True)
        result1 = await already_processed(
            redis_client=redis_mock,
            event_id=event_id,
            ttl_seconds=3600,
            prefix="event_processed",
        )
        assert result1 is False
        
        redis_mock.set = AsyncMock(return_value=False)
        result2 = await already_processed(
            redis_client=redis_mock,
            event_id=event_id,
            ttl_seconds=3600,
            prefix="event_processed",
        )
        assert result2 is True
    
    @pytest.mark.asyncio
    async def test_expired_event_can_be_reprocessed(self, redis_mock):
        event_id = "expired-event-123"
        short_ttl = 1
        
        redis_mock.set = AsyncMock(return_value=True)
        result1 = await already_processed(
            redis_client=redis_mock,
            event_id=event_id,
            ttl_seconds=short_ttl,
        )
        assert result1 is False
        
        redis_mock.set = AsyncMock(return_value=True)
        result2 = await already_processed(
            redis_client=redis_mock,
            event_id=event_id,
            ttl_seconds=short_ttl,
        )
        assert result2 is False

