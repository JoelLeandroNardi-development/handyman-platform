import aio_pika
from .config import RABBITMQ_URL

async def publish(exchange_name: str, routing_key: str, message: str):
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            exchange_name,
            aio_pika.ExchangeType.TOPIC
        )
        await exchange.publish(
            aio_pika.Message(body=message.encode()),
            routing_key=routing_key
        )
