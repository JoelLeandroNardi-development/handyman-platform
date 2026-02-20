import os
import aio_pika

RABBIT_URL = os.getenv("RABBIT_URL")
if not RABBIT_URL:
    raise RuntimeError("RABBIT_URL environment variable is not set")

EXCHANGE_NAME = "domain_events"


async def connect():
    return await aio_pika.connect_robust(RABBIT_URL)
