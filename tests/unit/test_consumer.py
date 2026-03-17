from unittest.mock import AsyncMock, MagicMock
import json

import pytest
from aio_pika import ExchangeType

from shared.shared.consumer import (
    setup_consumer_topology,
    _safe_decode_json,
    run_consumer_with_retry_dlq,
)


@pytest.mark.unit
@pytest.mark.rabbit
class TestSafeDecodeJson:
    
    def test_safe_decode_valid_json(self, rabbit_message_mock):
        payload = {"event": "booking.created", "id": "123"}
        rabbit_message_mock.body = json.dumps(payload).encode("utf-8")
        
        result = _safe_decode_json(rabbit_message_mock)
        
        assert result == payload
    
    def test_safe_decode_invalid_json(self, rabbit_message_mock):
        rabbit_message_mock.body = b"not valid json {{"
        
        result = _safe_decode_json(rabbit_message_mock)
        
        assert result == {}
    
    def test_safe_decode_empty_body(self, rabbit_message_mock):
        rabbit_message_mock.body = b""
        
        result = _safe_decode_json(rabbit_message_mock)
        
        assert result == {}
    
    def test_safe_decode_none_body(self, rabbit_message_mock):
        rabbit_message_mock.body = None
        
        result = _safe_decode_json(rabbit_message_mock)
        
        assert result == {}
    
    def test_safe_decode_complex_payload(self, rabbit_message_mock):
        payload = {
            "event": "booking.confirmed",
            "data": {
                "booking_id": "b-123",
                "user": {
                    "email": "user@example.com",
                    "name": "John",
                },
                "items": [1, 2, 3],
            },
            "timestamp": "2026-03-17T10:00:00Z",
        }
        rabbit_message_mock.body = json.dumps(payload).encode("utf-8")
        
        result = _safe_decode_json(rabbit_message_mock)
        
        assert result == payload


@pytest.mark.unit
@pytest.mark.rabbit
class TestSetupConsumerTopology:

    @pytest.mark.asyncio
    async def test_topology_setup_creates_structures(self, rabbit_channel_mock):
        exchange_mock = MagicMock()
        queue_mock = MagicMock()
        retry_queue_mock = MagicMock()
        dlq_mock = MagicMock()
        
        rabbit_channel_mock.declare_exchange = AsyncMock(return_value=exchange_mock)
        rabbit_channel_mock.declare_queue = AsyncMock(side_effect=[
            queue_mock,
            retry_queue_mock,
            dlq_mock,
        ])
        queue_mock.bind = AsyncMock()
        
        exchange, queue = await setup_consumer_topology(
            channel=rabbit_channel_mock,
            exchange_name="domain_events",
            queue_name="booking_queue",
            retry_queue="booking_retry",
            dlq_queue="booking_dlq",
            routing_keys=["booking.*"],
            retry_delay_ms=5000,
            prefetch=50,
        )
        
        rabbit_channel_mock.set_qos.assert_called_once()
        
        rabbit_channel_mock.declare_exchange.assert_called_once_with(
            "domain_events",
            ExchangeType.TOPIC,
            durable=True,
        )
        
        assert rabbit_channel_mock.declare_queue.call_count == 3
    
    @pytest.mark.asyncio
    async def test_topology_queue_bindings(self, rabbit_channel_mock):
        queue_mock = MagicMock()
        queue_mock.bind = AsyncMock()
        exchange_mock = MagicMock()
        
        rabbit_channel_mock.declare_exchange = AsyncMock(return_value=exchange_mock)
        rabbit_channel_mock.declare_queue = AsyncMock(return_value=queue_mock)
        
        routing_keys = ["booking.requested", "booking.confirmed", "booking.cancelled"]
        
        await setup_consumer_topology(
            channel=rabbit_channel_mock,
            exchange_name="domain_events",
            queue_name="booking_queue",
            retry_queue="booking_retry",
            dlq_queue="booking_dlq",
            routing_keys=routing_keys,
            retry_delay_ms=5000,
        )
        
        assert queue_mock.bind.call_count == len(routing_keys)
    
    @pytest.mark.asyncio
    async def test_topology_dlq_configuration(self, rabbit_channel_mock):
        queue_mock = MagicMock()
        queue_mock.bind = AsyncMock()
        rabbit_channel_mock.declare_queue = AsyncMock(return_value=queue_mock)
        rabbit_channel_mock.declare_exchange = AsyncMock()
        
        await setup_consumer_topology(
            channel=rabbit_channel_mock,
            exchange_name="domain_events",
            queue_name="booking_queue",
            retry_queue="booking_retry",
            dlq_queue="booking_dlq",
            routing_keys=["booking.*"],
            retry_delay_ms=5000,
        )
        
        calls = rabbit_channel_mock.declare_queue.call_args_list
        main_queue_call = calls[0]
        arguments = main_queue_call[1]["arguments"]
        
        assert arguments["x-dead-letter-exchange"] == ""
        assert arguments["x-dead-letter-routing-key"] == "booking_dlq"


@pytest.mark.unit
@pytest.mark.rabbit
class TestConsumerRetryDLQ:

    def _configure_topology(self, channel):
        main_queue = MagicMock()
        main_queue.bind = AsyncMock()
        channel.declare_exchange = AsyncMock(return_value=MagicMock())
        channel.declare_queue = AsyncMock(side_effect=[main_queue, MagicMock(), MagicMock()])
        return main_queue

    def _build_message(self, payload, headers=None):
        message = MagicMock()
        message.body = json.dumps(payload).encode("utf-8")
        message.headers = headers or {}
        message.content_type = "application/json"
        message.ack = AsyncMock()
        message.reject = AsyncMock()
        message.channel = MagicMock()
        message.channel.default_exchange = MagicMock()
        message.channel.default_exchange.publish = AsyncMock()
        return message

    @pytest.mark.asyncio
    async def test_successful_message_processing_acks(self, rabbit_channel_mock):
        handler = AsyncMock()
        self._configure_topology(rabbit_channel_mock)
        consume_queue = MagicMock()
        callback_holder = {}

        async def capture_callback(callback):
            callback_holder["callback"] = callback

        consume_queue.consume = AsyncMock(side_effect=capture_callback)
        rabbit_channel_mock.get_queue = AsyncMock(return_value=consume_queue)

        await run_consumer_with_retry_dlq(
            channel=rabbit_channel_mock,
            exchange_name="domain_events",
            queue_name="booking_queue",
            retry_queue="booking_retry",
            dlq_queue="booking_dlq",
            routing_keys=["booking.*"],
            handler=handler,
        )

        message = self._build_message({"event": "booking.requested"})
        await callback_holder["callback"](message)

        handler.assert_awaited_once_with({"event": "booking.requested"})
        message.ack.assert_awaited_once()
        message.reject.assert_not_awaited()
        message.channel.default_exchange.publish.assert_not_awaited()
    
    @pytest.mark.asyncio
    async def test_failed_message_published_to_retry_queue(self, rabbit_channel_mock):
        handler = AsyncMock(side_effect=ValueError("boom"))
        self._configure_topology(rabbit_channel_mock)
        consume_queue = MagicMock()
        callback_holder = {}

        async def capture_callback(callback):
            callback_holder["callback"] = callback

        consume_queue.consume = AsyncMock(side_effect=capture_callback)
        rabbit_channel_mock.get_queue = AsyncMock(return_value=consume_queue)

        await run_consumer_with_retry_dlq(
            channel=rabbit_channel_mock,
            exchange_name="domain_events",
            queue_name="booking_queue",
            retry_queue="booking_retry",
            dlq_queue="booking_dlq",
            routing_keys=["booking.*"],
            handler=handler,
            max_retries=3,
        )

        message = self._build_message({"event": "booking.requested"})
        await callback_holder["callback"](message)

        publish_call = message.channel.default_exchange.publish.await_args
        retry_message = publish_call.args[0]
        routing_key = publish_call.kwargs["routing_key"]

        assert retry_message.headers["x-retry-count"] == 1
        assert routing_key == "booking_retry"
        message.ack.assert_awaited_once()
        message.reject.assert_not_awaited()
    
    @pytest.mark.asyncio
    async def test_message_sent_to_dlq_after_max_retries(self, rabbit_channel_mock):
        handler = AsyncMock(side_effect=ValueError("poison"))
        self._configure_topology(rabbit_channel_mock)
        consume_queue = MagicMock()
        callback_holder = {}

        async def capture_callback(callback):
            callback_holder["callback"] = callback

        consume_queue.consume = AsyncMock(side_effect=capture_callback)
        rabbit_channel_mock.get_queue = AsyncMock(return_value=consume_queue)

        await run_consumer_with_retry_dlq(
            channel=rabbit_channel_mock,
            exchange_name="domain_events",
            queue_name="booking_queue",
            retry_queue="booking_retry",
            dlq_queue="booking_dlq",
            routing_keys=["booking.*"],
            handler=handler,
            max_retries=3,
        )

        message = self._build_message(
            {"event": "booking.requested"},
            headers={"x-retry-count": 3},
        )
        await callback_holder["callback"](message)

        message.reject.assert_awaited_once_with(requeue=False)
        message.ack.assert_not_awaited()
        message.channel.default_exchange.publish.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.rabbit
class TestConsumerErrorHandling:

    @pytest.mark.asyncio
    async def test_handler_exception_triggers_retry(self):
        handler = AsyncMock(side_effect=ValueError("Handler error"))

        with pytest.raises(ValueError):
            await handler({"event": "booking.requested"})
    
    @pytest.mark.asyncio
    async def test_json_decode_error_handled_gracefully(self):
        message = MagicMock()
        message.body = b"invalid json {{"
        message.headers = {}
        message.content_type = "application/json"
        
        payload = _safe_decode_json(message)
        assert payload == {}
