import os
import aio_pika
from aio_pika import ExchangeType

RABBIT_URL = os.getenv("RABBIT_URL")
EXCHANGE_NAME = "domain_events"


async def connect() -> aio_pika.RobustConnection | None:
    """
    Returns a robust connection when RABBIT_URL is configured, else None.
    Match-service should run fine without events in dev.
    """
    if not RABBIT_URL:
        return None
    return await aio_pika.connect_robust(RABBIT_URL)


async def declare_exchange(channel: aio_pika.abc.AbstractChannel):
    return await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)