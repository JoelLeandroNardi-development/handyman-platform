from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.core.messaging.mq import RabbitConfig, RabbitPublisher, create_publisher, rabbit_connect

@pytest.mark.unit
class TestRabbitConfig:
    def test_default_exchange(self, monkeypatch):
        monkeypatch.setenv("RABBIT_URL", "amqp://guest:guest@localhost/")
        monkeypatch.delenv("EXCHANGE_NAME", raising=False)
        cfg = RabbitConfig.from_env()
        assert cfg.url == "amqp://guest:guest@localhost/"
        assert cfg.exchange_name == "domain_events"

    def test_blank_exchange_normalizes(self, monkeypatch):
        monkeypatch.setenv("RABBIT_URL", "amqp://guest:guest@localhost/")
        monkeypatch.setenv("EXCHANGE_NAME", "   ")
        assert RabbitConfig.from_env().exchange_name == "domain_events"

    def test_required_url_raises(self, monkeypatch):
        monkeypatch.delenv("RABBIT_URL", raising=False)
        with pytest.raises(RuntimeError):
            RabbitConfig.from_env(required=True)

@pytest.mark.unit
class TestRabbitPublisher:
    @pytest.mark.asyncio
    async def test_start_noop_when_disabled(self):
        pub = RabbitPublisher(RabbitConfig(url=None, exchange_name="events"))
        await pub.start()
        assert pub._conn is None

    @pytest.mark.asyncio
    async def test_start_connects(self, monkeypatch):
        conn = MagicMock(is_closed=False)
        ch = MagicMock()
        ex = MagicMock()
        conn.channel = AsyncMock(return_value=ch)
        ch.declare_exchange = AsyncMock(return_value=ex)
        monkeypatch.setattr("shared.core.messaging.mq.aio_pika.connect_robust", AsyncMock(return_value=conn))

        pub = RabbitPublisher(RabbitConfig(url="amqp://localhost/", exchange_name="events"))
        await pub.start()
        assert pub._exchange is ex

    @pytest.mark.asyncio
    async def test_start_no_reconnect_when_ready(self, monkeypatch):
        pub = RabbitPublisher(RabbitConfig(url="amqp://localhost/", exchange_name="events"))
        pub._conn = MagicMock(is_closed=False)
        pub._exchange = MagicMock()
        connect = AsyncMock()
        monkeypatch.setattr("shared.core.messaging.mq.aio_pika.connect_robust", connect)
        await pub.start()
        connect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_start_closes_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            "shared.core.messaging.mq.aio_pika.connect_robust",
            AsyncMock(side_effect=RuntimeError("boom")),
        )
        pub = RabbitPublisher(RabbitConfig(url="amqp://localhost/", exchange_name="events"))
        pub.close = AsyncMock()
        await pub.start()
        pub.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_ignores_errors(self):
        pub = RabbitPublisher(RabbitConfig(url="amqp://localhost/", exchange_name="events"))
        pub._channel = MagicMock(is_closed=False, close=AsyncMock(side_effect=RuntimeError))
        pub._conn = MagicMock(is_closed=False, close=AsyncMock(side_effect=RuntimeError))
        await pub.close()
        assert pub._channel is None and pub._conn is None

    @pytest.mark.asyncio
    async def test_close_handles_real_resources(self):
        pub = RabbitPublisher(RabbitConfig(url="amqp://localhost/", exchange_name="events"))
        ch = MagicMock(is_closed=False, close=AsyncMock())
        conn = MagicMock(is_closed=False, close=AsyncMock())
        pub._channel, pub._conn, pub._exchange = ch, conn, MagicMock()
        await pub.close()
        ch.close.assert_awaited_once()
        conn.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_ready_raises_when_disabled(self):
        pub = RabbitPublisher(RabbitConfig(url=None, exchange_name="events"))
        with pytest.raises(RuntimeError):
            await pub._ensure_ready()

    @pytest.mark.asyncio
    async def test_publish_noop_when_disabled(self):
        pub = RabbitPublisher(RabbitConfig(url=None, exchange_name="events"))
        await pub.publish(routing_key="booking.requested", payload={"id": 1})
        assert pub._exchange is None

    @pytest.mark.asyncio
    async def test_publish_requires_routing_key(self):
        pub = RabbitPublisher(RabbitConfig(url="amqp://localhost/", exchange_name="events"))
        with pytest.raises(ValueError):
            await pub.publish(routing_key="   ", payload={"id": 1})

    @pytest.mark.asyncio
    async def test_publish_sends_json(self):
        pub = RabbitPublisher(RabbitConfig(url="amqp://localhost/", exchange_name="events"))
        pub._ensure_ready = AsyncMock()
        pub._exchange = MagicMock(publish=AsyncMock())

        await pub.publish(
            routing_key="booking.requested",
            payload={"msg": "olá", "n": 2},
            message_id="evt-1", headers={"x-test": "1"}, mandatory=False,
        )

        msg = pub._exchange.publish.await_args.args[0]
        assert json.loads(msg.body) == {"msg": "olá", "n": 2}
        assert msg.message_id == "evt-1"
        assert pub._exchange.publish.await_args.kwargs["routing_key"] == "booking.requested"

    @pytest.mark.asyncio
    async def test_publish_reraises(self):
        pub = RabbitPublisher(RabbitConfig(url="amqp://localhost/", exchange_name="events"))
        pub._ensure_ready = AsyncMock()
        pub._exchange = MagicMock(publish=AsyncMock(side_effect=RuntimeError("fail")))
        with pytest.raises(RuntimeError):
            await pub.publish(routing_key="booking.requested", payload={"id": 1})


@pytest.mark.unit
class TestRabbitHelpers:
    @pytest.mark.asyncio
    async def test_connect_none_without_url(self):
        assert await rabbit_connect(RabbitConfig(url=None, exchange_name="events")) is None

    @pytest.mark.asyncio
    async def test_connect_uses_aio_pika(self, monkeypatch):
        conn = MagicMock()
        monkeypatch.setattr(
            "shared.core.messaging.mq.aio_pika.connect_robust",
            AsyncMock(return_value=conn),
        )
        assert await rabbit_connect(RabbitConfig(url="amqp://localhost/", exchange_name="events")) is conn

    def test_create_publisher(self, monkeypatch):
        monkeypatch.setenv("RABBIT_URL", "amqp://localhost/")
        monkeypatch.setenv("EXCHANGE_NAME", "domain_events")
        pub, cfg = create_publisher(required=False)
        assert isinstance(cfg, RabbitConfig) and pub.enabled is True