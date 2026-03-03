import os
import json
import aio_pika
from aio_pika import ExchangeType

RABBIT_URL = os.getenv("RABBIT_URL")  # optional in dev
EXCHANGE_NAME = "domain_events"


class Publisher:
    """
    Best-effort publisher.
    Availability uses a Redis outbox to buffer events when RabbitMQ is down.
    """
    def __init__(self):
        self.enabled = bool(RABBIT_URL)
        self._conn: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def start(self):
        if not self.enabled:
            return
        if self._conn and not self._conn.is_closed:
            return

        self._conn = await aio_pika.connect_robust(RABBIT_URL)
        self._channel = await self._conn.channel()
        self._exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )

    async def close(self):
        try:
            if self._conn and not self._conn.is_closed:
                await self._conn.close()
        except Exception:
            pass
        finally:
            self._conn = None
            self._channel = None
            self._exchange = None

    async def publish(self, routing_key: str, payload: dict):
        if not self.enabled:
            return
        if not self._exchange:
            # try lazy start once; if it fails, caller should rely on outbox retry
            await self.start()
            if not self._exchange:
                raise RuntimeError("publisher not ready")

        body = json.dumps(payload).encode("utf-8")
        msg = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(msg, routing_key=routing_key)


publisher = Publisher()