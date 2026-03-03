import os
import json
from typing import Optional

import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode

RABBIT_URL = os.getenv("RABBIT_URL")
if not RABBIT_URL:
    raise RuntimeError("RABBIT_URL environment variable is not set")

EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "domain_events")


class RabbitMQ:
    """
    One shared connection per service process.
    We keep separate channels for publish and consume.
    """
    def __init__(self) -> None:
        self._conn: Optional[aio_pika.RobustConnection] = None
        self._pub_channel: Optional[aio_pika.RobustChannel] = None
        self._pub_exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> aio_pika.RobustConnection:
        if self._conn and not self._conn.is_closed:
            return self._conn
        self._conn = await aio_pika.connect_robust(RABBIT_URL)
        return self._conn

    async def get_publish_exchange(self) -> aio_pika.Exchange:
        if self._pub_exchange and self._pub_channel and not self._pub_channel.is_closed:
            return self._pub_exchange

        conn = await self.connect()
        self._pub_channel = await conn.channel(publisher_confirms=True)
        self._pub_exchange = await self._pub_channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.TOPIC, durable=True
        )
        return self._pub_exchange

    async def publish_json(self, routing_key: str, payload: dict, message_id: str) -> None:
        ex = await self.get_publish_exchange()
        body = json.dumps(payload, default=str).encode("utf-8")
        msg = Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=message_id,
        )
        await ex.publish(msg, routing_key=routing_key)

    async def new_consumer_channel(self, prefetch: int = 50) -> aio_pika.RobustChannel:
        conn = await self.connect()
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=prefetch)
        return ch

    async def close(self) -> None:
        try:
            if self._pub_channel and not self._pub_channel.is_closed:
                await self._pub_channel.close()
        except Exception:
            pass
        self._pub_channel = None
        self._pub_exchange = None

        try:
            if self._conn and not self._conn.is_closed:
                await self._conn.close()
        except Exception:
            pass
        self._conn = None


mq = RabbitMQ()