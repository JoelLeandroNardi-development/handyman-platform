import aio_pika
from .rabbitmq import connect, EXCHANGE_NAME

class Publisher:
    def __init__(self):
        self._conn = None
        self._channel = None
        self._exchange = None

    async def start(self):
        if self._conn and not self._conn.is_closed:
            return
        self._conn = await connect()
        self._channel = await self._conn.channel()
        self._exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def publish(self, routing_key: str, body: str):
        await self.start()
        msg = aio_pika.Message(
            body=body.encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(msg, routing_key=routing_key)

    async def close(self):
        if self._conn and not self._conn.is_closed:
            await self._conn.close()

publisher = Publisher()