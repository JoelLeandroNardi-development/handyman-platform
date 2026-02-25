import os
import aio_pika

RABBIT_URL = os.getenv("RABBIT_URL")  # optional in dev, required if you want events

EXCHANGE_NAME = "domain_events"


class RabbitPublisher:
    def __init__(self):
        self.enabled = bool(RABBIT_URL)
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self):
        if not self.enabled:
            return

        if self._connection and not self._connection.is_closed:
            return

        try:
            self._connection = await aio_pika.connect_robust(RABBIT_URL)
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                EXCHANGE_NAME,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
        except Exception as e:
            print(f"[user-service] RabbitMQ connect failed: {e}")
            self._connection = None
            self._channel = None
            self._exchange = None
            raise

    async def publish(self, routing_key: str, message_body: str):
        if not self.enabled:
            return

        try:
            await self.connect()
        except Exception:
            return

        if not self._exchange:
            return

        try:
            msg = aio_pika.Message(
                body=message_body.encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await self._exchange.publish(msg, routing_key=routing_key)
        except Exception as e:
            print(f"[user-service] RabbitMQ publish failed: {e}")

    async def close(self):
        try:
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
        finally:
            self._connection = None
            self._channel = None
            self._exchange = None


publisher = RabbitPublisher()
