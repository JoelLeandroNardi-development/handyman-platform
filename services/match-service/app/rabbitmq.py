import os
import aio_pika

RABBIT_URL = os.getenv("RABBIT_URL")  # required if you want events
EXCHANGE_NAME = "domain_events"


async def connect():
    if not RABBIT_URL:
        return None
    return await aio_pika.connect_robust(RABBIT_URL)
