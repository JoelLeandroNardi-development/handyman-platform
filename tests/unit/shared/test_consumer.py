from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aio_pika import ExchangeType

from shared.core.messaging.consumer import (
    setup_consumer_topology,
    _safe_decode_json,
    run_consumer_with_retry_dlq,
)

@pytest.mark.unit
@pytest.mark.rabbit
class TestSafeDecodeJson:
    @pytest.mark.parametrize("raw, expected", [
        (json.dumps({"event": "booking.created"}).encode(), {"event": "booking.created"}),
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
            "event": "booking.confirmed",
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
            channel=rabbit_channel_mock, exchange_name="domain_events",
            queue_name="q", retry_queue="q_retry", dlq_queue="q_dlq",
            routing_keys=["booking.*"], retry_delay_ms=5000, prefetch=50,
        )

        rabbit_channel_mock.set_qos.assert_called_once()
        rabbit_channel_mock.declare_exchange.assert_called_once_with("domain_events", ExchangeType.TOPIC, durable=True)
        assert rabbit_channel_mock.declare_queue.call_count == 3

    @pytest.mark.asyncio
    async def test_binds_all_routing_keys(self, rabbit_channel_mock):
        queue = MagicMock(bind=AsyncMock())
        rabbit_channel_mock.declare_exchange = AsyncMock(return_value=MagicMock())
        rabbit_channel_mock.declare_queue = AsyncMock(return_value=queue)

        rks = ["booking.requested", "booking.confirmed", "booking.cancelled"]
        await setup_consumer_topology(
            channel=rabbit_channel_mock, exchange_name="domain_events",
            queue_name="q", retry_queue="q_retry", dlq_queue="q_dlq",
            routing_keys=rks, retry_delay_ms=5000,
        )
        assert queue.bind.call_count == len(rks)

    @pytest.mark.asyncio
    async def test_dlq_configuration(self, rabbit_channel_mock):
        queue = MagicMock(bind=AsyncMock())
        rabbit_channel_mock.declare_queue = AsyncMock(return_value=queue)
        rabbit_channel_mock.declare_exchange = AsyncMock()

        await setup_consumer_topology(
            channel=rabbit_channel_mock, exchange_name="domain_events",
            queue_name="q", retry_queue="q_retry", dlq_queue="q_dlq",
            routing_keys=["booking.*"], retry_delay_ms=5000,
        )

        args = rabbit_channel_mock.declare_queue.call_args_list[0][1]["arguments"]
        assert args["x-dead-letter-exchange"] == ""
        assert args["x-dead-letter-routing-key"] == "q_dlq"

def _configure_topology(channel):
    queue = MagicMock(bind=AsyncMock())
    channel.declare_exchange = AsyncMock(return_value=MagicMock())
    channel.declare_queue = AsyncMock(side_effect=[queue, MagicMock(), MagicMock()])
    return queue

def _build_message(payload, headers=None):
    msg = MagicMock()
    msg.body = json.dumps(payload).encode()
    msg.headers = headers or {}
    msg.content_type = "application/json"
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
        channel=channel, exchange_name="domain_events",
        queue_name="q", retry_queue="q_retry", dlq_queue="q_dlq",
        routing_keys=["booking.*"], handler=handler, **run_kwargs,
    )
    await holder["cb"](msg)

@pytest.mark.unit
@pytest.mark.rabbit
class TestConsumerRetryDLQ:
    @pytest.mark.asyncio
    async def test_success_acks(self, rabbit_channel_mock):
        handler = AsyncMock()
        msg = _build_message({"event": "booking.requested"})
        await _capture_and_invoke(rabbit_channel_mock, handler, msg=msg)

        handler.assert_awaited_once_with({"event": "booking.requested"})
        msg.ack.assert_awaited_once()
        msg.reject.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failure_publishes_to_retry(self, rabbit_channel_mock):
        handler = AsyncMock(side_effect=ValueError("boom"))
        msg = _build_message({"event": "booking.requested"})
        await _capture_and_invoke(rabbit_channel_mock, handler, msg=msg, max_retries=3)

        pub = msg.channel.default_exchange.publish.await_args
        assert pub.args[0].headers["x-retry-count"] == 1
        assert pub.kwargs["routing_key"] == "q_retry"
        msg.ack.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_max_retries_rejects_to_dlq(self, rabbit_channel_mock):
        handler = AsyncMock(side_effect=ValueError("poison"))
        msg = _build_message({"event": "booking.requested"}, headers={"x-retry-count": 3})
        await _capture_and_invoke(rabbit_channel_mock, handler, msg=msg, max_retries=3)

        msg.reject.assert_awaited_once_with(requeue=False)
        msg.ack.assert_not_awaited()