from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.shared.mq import RabbitConfig, RabbitPublisher, create_publisher, rabbit_connect


@pytest.mark.unit
class TestRabbitConfig:

    def test_from_env_uses_default_exchange(self, monkeypatch):
        monkeypatch.setenv("RABBIT_URL", "amqp://guest:guest@localhost/")
        monkeypatch.delenv("EXCHANGE_NAME", raising=False)

        cfg = RabbitConfig.from_env()

        assert cfg.url == "amqp://guest:guest@localhost/"
        assert cfg.exchange_name == "domain_events"

    def test_from_env_normalizes_blank_exchange_name(self, monkeypatch):
        monkeypatch.setenv("RABBIT_URL", "amqp://guest:guest@localhost/")
        monkeypatch.setenv("EXCHANGE_NAME", "   ")

        cfg = RabbitConfig.from_env()

        assert cfg.exchange_name == "domain_events"

    def test_from_env_requires_url_when_requested(self, monkeypatch):
        monkeypatch.delenv("RABBIT_URL", raising=False)

        with pytest.raises(RuntimeError):
            RabbitConfig.from_env(required=True)


@pytest.mark.unit
class TestRabbitPublisher:

    @pytest.mark.asyncio
    async def test_start_noops_when_disabled(self):
        publisher = RabbitPublisher(RabbitConfig(url=None, exchange_name="domain_events"))

        await publisher.start()

        assert publisher._conn is None
        assert publisher._exchange is None

    @pytest.mark.asyncio
    async def test_start_connects_and_declares_exchange(self, monkeypatch):
        connection = MagicMock()
        connection.is_closed = False
        channel = MagicMock()
        exchange = MagicMock()
        connection.channel = AsyncMock(return_value=channel)
        channel.declare_exchange = AsyncMock(return_value=exchange)
        connect = AsyncMock(return_value=connection)
        monkeypatch.setattr("shared.shared.mq.aio_pika.connect_robust", connect)

        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))
        await publisher.start()

        connect.assert_awaited_once_with("amqp://guest:guest@localhost/")
        connection.channel.assert_awaited_once_with(publisher_confirms=True)
        channel.declare_exchange.assert_awaited_once()
        assert publisher._exchange is exchange

    @pytest.mark.asyncio
    async def test_start_does_not_reconnect_when_already_ready(self, monkeypatch):
        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))
        publisher._conn = MagicMock(is_closed=False)
        publisher._exchange = MagicMock()
        connect = AsyncMock()
        monkeypatch.setattr("shared.shared.mq.aio_pika.connect_robust", connect)

        await publisher.start()

        connect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_start_closes_resources_when_connect_fails(self, monkeypatch):
        connect = AsyncMock(side_effect=RuntimeError("connect failed"))
        monkeypatch.setattr("shared.shared.mq.aio_pika.connect_robust", connect)

        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))
        publisher.close = AsyncMock()
        await publisher.start()

        publisher.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_ignores_channel_close_errors(self):
        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))
        channel = MagicMock(is_closed=False)
        channel.close = AsyncMock(side_effect=RuntimeError("close failed"))
        connection = MagicMock(is_closed=False)
        connection.close = AsyncMock(side_effect=RuntimeError("conn failed"))
        publisher._channel = channel
        publisher._conn = connection

        await publisher.close()

        assert publisher._channel is None
        assert publisher._conn is None

    @pytest.mark.asyncio
    async def test_close_handles_existing_channel_and_connection(self):
        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))
        channel = MagicMock(is_closed=False)
        channel.close = AsyncMock()
        connection = MagicMock(is_closed=False)
        connection.close = AsyncMock()
        publisher._channel = channel
        publisher._conn = connection
        publisher._exchange = MagicMock()

        await publisher.close()

        channel.close.assert_awaited_once()
        connection.close.assert_awaited_once()
        assert publisher._channel is None
        assert publisher._conn is None
        assert publisher._exchange is None

    @pytest.mark.asyncio
    async def test_ensure_ready_raises_when_disabled(self):
        publisher = RabbitPublisher(RabbitConfig(url=None, exchange_name="events"))

        with pytest.raises(RuntimeError):
            await publisher._ensure_ready()

    @pytest.mark.asyncio
    async def test_ensure_ready_reuses_existing_exchange(self):
        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))
        publisher._conn = MagicMock(is_closed=False)
        publisher._exchange = MagicMock()

        await publisher._ensure_ready()

        assert publisher._exchange is not None

    @pytest.mark.asyncio
    async def test_publish_noops_when_disabled(self):
        publisher = RabbitPublisher(RabbitConfig(url=None, exchange_name="events"))

        await publisher.publish(routing_key="booking.requested", payload={"id": 1})

        assert publisher._exchange is None

    @pytest.mark.asyncio
    async def test_publish_requires_routing_key(self):
        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))

        with pytest.raises(ValueError):
            await publisher.publish(routing_key="   ", payload={"id": 1})

    @pytest.mark.asyncio
    async def test_publish_sends_json_message(self):
        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))
        publisher._ensure_ready = AsyncMock()
        publisher._exchange = MagicMock()
        publisher._exchange.publish = AsyncMock()

        await publisher.publish(
            routing_key="booking.requested",
            payload={"message": "olá", "count": 2},
            message_id="evt-1",
            headers={"x-test": "1"},
            mandatory=False,
        )

        call = publisher._exchange.publish.await_args
        message = call.args[0]
        assert json.loads(message.body.decode("utf-8")) == {"message": "olá", "count": 2}
        assert message.message_id == "evt-1"
        assert message.headers == {"x-test": "1"}
        assert call.kwargs["routing_key"] == "booking.requested"
        assert call.kwargs["mandatory"] is False

    @pytest.mark.asyncio
    async def test_publish_reraises_exchange_errors(self):
        publisher = RabbitPublisher(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))
        publisher._ensure_ready = AsyncMock()
        publisher._exchange = MagicMock()
        publisher._exchange.publish = AsyncMock(side_effect=RuntimeError("publish failed"))

        with pytest.raises(RuntimeError):
            await publisher.publish(routing_key="booking.requested", payload={"id": 1})


@pytest.mark.unit
class TestRabbitHelpers:

    @pytest.mark.asyncio
    async def test_rabbit_connect_returns_none_without_url(self):
        result = await rabbit_connect(RabbitConfig(url=None, exchange_name="events"))

        assert result is None

    @pytest.mark.asyncio
    async def test_rabbit_connect_uses_aio_pika(self, monkeypatch):
        connection = MagicMock()
        connect = AsyncMock(return_value=connection)
        monkeypatch.setattr("shared.shared.mq.aio_pika.connect_robust", connect)

        result = await rabbit_connect(RabbitConfig(url="amqp://guest:guest@localhost/", exchange_name="events"))

        assert result is connection
        connect.assert_awaited_once_with("amqp://guest:guest@localhost/")

    def test_create_publisher_returns_config_and_publisher(self, monkeypatch):
        monkeypatch.setenv("RABBIT_URL", "amqp://guest:guest@localhost/")
        monkeypatch.setenv("EXCHANGE_NAME", "domain_events")

        publisher, cfg = create_publisher(required=False)

        assert isinstance(cfg, RabbitConfig)
        assert publisher.cfg == cfg
        assert publisher.enabled is True