import os
import json
import aio_pika
from aio_pika import ExchangeType

RABBIT_URL = os.getenv("RABBIT_URL")
if not RABBIT_URL:
    raise RuntimeError("RABBIT_URL is not set")

EXCHANGE_NAME = "domain_events"


class Publisher:
    def __init__(self):
        self._conn: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def start(self):
        # idempotent start
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
        if not self._exchange:
            raise RuntimeError("Publisher not started")

        body = json.dumps(payload).encode("utf-8")
        msg = aio_pika.Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._exchange.publish(msg, routing_key=routing_key)


publisher = Publisher()