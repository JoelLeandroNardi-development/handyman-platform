import os
import aio_pika
from aio_pika import ExchangeType

RABBIT_URL = os.getenv("RABBIT_URL")
EXCHANGE_NAME = "domain_events"


class Publisher:
    def __init__(self):
        self._conn = None
        self._channel = None
        self._exchange = None

    async def start(self):
        if not RABBIT_URL:
            raise RuntimeError("RABBIT_URL is not set")

        self._conn = await aio_pika.connect_robust(RABBIT_URL)
        self._channel = await self._conn.channel()
        self._exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.TOPIC, durable=True
        )

    async def close(self):
        try:
            if self._conn and not self._conn.is_closed:
                await self._conn.close()
        except Exception:
            pass

    async def publish(self, routing_key: str, payload: dict):
        if not self._exchange:
            raise RuntimeError("Publisher not started")

        msg = aio_pika.Message(
            body=aio_pika.serialization.JsonSerializer.dumps(payload),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._exchange.publish(msg, routing_key=routing_key)


publisher = Publisher()