import json
import aio_pika
from aio_pika import ExchangeType

from .rabbitmq import connect, EXCHANGE_NAME
from .services import redis_client

QUEUE_NAME = "match_service_availability_events"
ROUTING_KEY = "availability.updated"

IDEMPOTENCY_TTL_SECONDS = 60 * 60  # 1 hour


async def _already_processed(event_id: str) -> bool:
    key = f"processed_event:{event_id}"
    exists = await redis_client.get(key)
    if exists:
        return True
    await redis_client.set(key, "1", ex=IDEMPOTENCY_TTL_SECONDS)
    return False


async def _invalidate_match_cache():
    """
    Coarse invalidation:
    delete match:* keys. Safe in early stage.
    """
    pattern = "match:*"
    cursor = 0
    keys_to_delete = []

    while True:
        cursor, keys = await redis_client.scan(cursor=cursor, match=pattern, count=500)
        if keys:
            keys_to_delete.extend(keys)
        if cursor == 0:
            break

    if keys_to_delete:
        # Redis can delete multiple keys at once
        await redis_client.delete(*keys_to_delete)


async def handle_message(message: aio_pika.IncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except Exception:
            return

        event_id = payload.get("event_id")
        event_type = payload.get("event_type")

        if not event_id or event_type != "availability.updated":
            return

        if await _already_processed(event_id):
            return

        # Invalidate cached match responses so new availability reflects quickly
        await _invalidate_match_cache()


async def start_consumer():
    connection = await connect()
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=50)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        ExchangeType.TOPIC,
        durable=True,
    )

    queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
    )

    await queue.bind(exchange, routing_key=ROUTING_KEY)
    await queue.consume(handle_message)

    return connection
