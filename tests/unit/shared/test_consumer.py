from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aio_pika import ExchangeType

from tests.constants import (
    EventType,
    CONTENT_TYPE_JSON,
    DLQ_QUEUE_NAME_DEFAULT,
    EXCHANGE_DOMAIN_EVENTS,
    HEADER_RETRY_COUNT,
    MAX_RETRIES,
    QUEUE_NAME_DEFAULT,
    RETRY_DELAY_MS,
    RETRY_QUEUE_NAME_DEFAULT,
    ROUTING_KEY_BOOKING_WILDCARD,
)
from shared.core.messaging.consumer import (
    setup_consumer_topology,
    _safe_decode_json,
    run_consumer_with_retry_dlq,
)

@pytest.mark.unit
@pytest.mark.rabbit
class TestSafeDecodeJson:
    @pytest.mark.parametrize("raw, expected", [
        (json.dumps({"event": EventType.BOOKING_CREATED}).encode(), {"event": EventType.BOOKING_CREATED}),
        (b"not valid json {{", {}),
        (b"", {}),
        (None, {}),
        (b"\x80\x81\x82", {}),
    ], ids=["valid", "invalid", "empty", "none", "binary"])
    def test_decode(self, raw, expected, rabbit_message_mock):
        rabbit_message_mock.body = raw
        assert _safe_decode_json(rabbit_message_mock) == expected

    def test_complex_payload(self, rabbit_message_mock):
        payload = {
            "event": EventType.BOOKING_CONFIRMED,
            "data": {"booking_id": "b-123", "items": [1, 2, 3]},
        }
        rabbit_message_mock.body = json.dumps(payload).encode()
        assert _safe_decode_json(rabbit_message_mock) == payload

@pytest.mark.unit
@pytest.mark.rabbit
class TestSetupConsumerTopology:
    @pytest.mark.asyncio
    async def test_creates_all_structures(self, rabbit_channel_mock):
        exchange = MagicMock()
        queue = MagicMock(bind=AsyncMock())
        rabbit_channel_mock.declare_exchange = AsyncMock(return_value=exchange)
        rabbit_channel_mock.declare_queue = AsyncMock(side_effect=[queue, MagicMock(), MagicMock()])

        await setup_consumer_topology(
            channel=rabbit_channel_mock,
            exchange_name=EXCHANGE_DOMAIN_EVENTS,
            queue_name=QUEUE_NAME_DEFAULT,
            retry_queue=RETRY_QUEUE_NAME_DEFAULT,
            dlq_queue=DLQ_QUEUE_NAME_DEFAULT,
            routing_keys=[ROUTING_KEY_BOOKING_WILDCARD],
            retry_delay_ms=RETRY_DELAY_MS,
            prefetch=50,
        )

        rabbit_channel_mock.set_qos.assert_called_once()
        rabbit_channel_mock.declare_exchange.assert_called_once_with(EXCHANGE_DOMAIN_EVENTS, ExchangeType.TOPIC, durable=True)
        assert rabbit_channel_mock.declare_queue.call_count == 3

    @pytest.mark.asyncio
    async def test_binds_all_routing_keys(self, rabbit_channel_mock):
        queue = MagicMock(bind=AsyncMock())
        rabbit_channel_mock.declare_exchange = AsyncMock(return_value=MagicMock())
        rabbit_channel_mock.declare_queue = AsyncMock(return_value=queue)

        rks = [EventType.BOOKING_REQUESTED, EventType.BOOKING_CONFIRMED, EventType.BOOKING_CANCELLED]
        await setup_consumer_topology(
            channel=rabbit_channel_mock,
            exchange_name=EXCHANGE_DOMAIN_EVENTS,
            queue_name=QUEUE_NAME_DEFAULT,
            retry_queue=RETRY_QUEUE_NAME_DEFAULT,
            dlq_queue=DLQ_QUEUE_NAME_DEFAULT,
            routing_keys=rks,
            retry_delay_ms=RETRY_DELAY_MS,
        )
        assert queue.bind.call_count == len(rks)

    @pytest.mark.asyncio
    async def test_dlq_configuration(self, rabbit_channel_mock):
        queue = MagicMock(bind=AsyncMock())
        rabbit_channel_mock.declare_queue = AsyncMock(return_value=queue)
        rabbit_channel_mock.declare_exchange = AsyncMock()

        await setup_consumer_topology(
            channel=rabbit_channel_mock,
            exchange_name=EXCHANGE_DOMAIN_EVENTS,
            queue_name=QUEUE_NAME_DEFAULT,
            retry_queue=RETRY_QUEUE_NAME_DEFAULT,
            dlq_queue=DLQ_QUEUE_NAME_DEFAULT,
            routing_keys=[ROUTING_KEY_BOOKING_WILDCARD],
            retry_delay_ms=RETRY_DELAY_MS,
        )

        args = rabbit_channel_mock.declare_queue.call_args_list[0][1]["arguments"]
        assert args["x-dead-letter-exchange"] == ""
        assert args["x-dead-letter-routing-key"] == DLQ_QUEUE_NAME_DEFAULT

def _configure_topology(channel):
    queue = MagicMock(bind=AsyncMock())
    channel.declare_exchange = AsyncMock(return_value=MagicMock())
    channel.declare_queue = AsyncMock(side_effect=[queue, MagicMock(), MagicMock()])
    return queue

def _build_message(payload, headers=None):
    msg = MagicMock()
    msg.body = json.dumps(payload).encode()
    msg.headers = headers or {}
    msg.content_type = CONTENT_TYPE_JSON
    msg.ack = AsyncMock()
    msg.reject = AsyncMock()
    msg.channel = MagicMock()
    msg.channel.default_exchange = MagicMock(publish=AsyncMock())
    return msg

async def _capture_and_invoke(channel, handler, *, msg, **run_kwargs):
    _configure_topology(channel)
    holder = {}
    consume_queue = MagicMock()

    async def _capture(callback):
        holder["cb"] = callback

    consume_queue.consume = AsyncMock(side_effect=_capture)
    channel.get_queue = AsyncMock(return_value=consume_queue)

    await run_consumer_with_retry_dlq(
        channel=channel,
        exchange_name=EXCHANGE_DOMAIN_EVENTS,
        queue_name=QUEUE_NAME_DEFAULT,
        retry_queue=RETRY_QUEUE_NAME_DEFAULT,
        dlq_queue=DLQ_QUEUE_NAME_DEFAULT,
        routing_keys=[ROUTING_KEY_BOOKING_WILDCARD],
        handler=handler,
        **run_kwargs,
    )
    await holder["cb"](msg)

@pytest.mark.unit
@pytest.mark.rabbit
class TestConsumerRetryDLQ:
    @pytest.mark.asyncio
    async def test_success_acks(self, rabbit_channel_mock):
        handler = AsyncMock()
        msg = _build_message({"event": EventType.BOOKING_REQUESTED})
        await _capture_and_invoke(rabbit_channel_mock, handler, msg=msg)

        handler.assert_awaited_once_with({"event": EventType.BOOKING_REQUESTED})
        msg.ack.assert_awaited_once()
        msg.reject.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failure_publishes_to_retry(self, rabbit_channel_mock):
        handler = AsyncMock(side_effect=ValueError("boom"))
        msg = _build_message({"event": EventType.BOOKING_REQUESTED})
        await _capture_and_invoke(rabbit_channel_mock, handler, msg=msg, max_retries=MAX_RETRIES)

        pub = msg.channel.default_exchange.publish.await_args
        assert pub.args[0].headers[HEADER_RETRY_COUNT] == 1
        assert pub.kwargs["routing_key"] == RETRY_QUEUE_NAME_DEFAULT
        msg.ack.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_max_retries_rejects_to_dlq(self, rabbit_channel_mock):
        handler = AsyncMock(side_effect=ValueError("poison"))
        msg = _build_message({"event": EventType.BOOKING_REQUESTED}, headers={HEADER_RETRY_COUNT: MAX_RETRIES})
        await _capture_and_invoke(rabbit_channel_mock, handler, msg=msg, max_retries=MAX_RETRIES)

        msg.reject.assert_awaited_once_with(requeue=False)
        msg.ack.assert_not_awaited()