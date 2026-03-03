import asyncio
import json
import aio_pika
from aio_pika import ExchangeType, Message

from .messaging import connect, EXCHANGE_NAME, declare_exchange
from .services import (
    redis_client,
    invalidate_bucket,
    buckets_in_radius,
    fetch_handyman,
    norm,
)

QUEUE_NAME = "match_service_domain_events"
RETRY_QUEUE = "match_service_domain_events_retry"
DLQ_QUEUE = "match_service_domain_events_dlq"

# Only include events we actually use for cache invalidation
ROUTING_KEYS = [
    "availability.updated",
    "handyman.created",
    "handyman.location_updated",
]

MAX_RETRIES = 3
RETRY_DELAY_MS = 5000
IDEMPOTENCY_TTL_SECONDS = 3600
RETRY_SECONDS = 5


async def _already_processed(event_id: str) -> bool:
    key = f"processed_event:{event_id}"
    if await redis_client.get(key):
        return True
    await redis_client.set(key, "1", ex=IDEMPOTENCY_TTL_SECONDS)
    return False


async def _invalidate_for_handyman_profile(profile: dict | None):
    if not profile:
        return

    lat = profile.get("latitude")
    lon = profile.get("longitude")
    radius = profile.get("service_radius_km")
    skills = profile.get("skills") or []

    if lat is None or lon is None or radius is None:
        return

    skills = [norm(s) for s in skills if s]
    if not skills:
        return

    buckets = buckets_in_radius(float(lat), float(lon), float(radius))

    for skill in skills:
        for mode in ("strict", "degraded"):
            for b_lat, b_lon in buckets:
                await invalidate_bucket(mode, skill, b_lat, b_lon)


async def process_event(payload: dict):
    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    data = payload.get("data") or {}

    if not event_id or not event_type:
        return

    if event_type not in ROUTING_KEYS:
        return

    if await _already_processed(event_id):
        return

    if event_type == "availability.updated":
        email = data.get("email")
        if email:
            profile = await fetch_handyman(email)
            await _invalidate_for_handyman_profile(profile)
        return

    if event_type == "handyman.created":
        await _invalidate_for_handyman_profile(data)
        return

    if event_type == "handyman.location_updated":
        email = data.get("email")
        if email:
            profile = await fetch_handyman(email)
            await _invalidate_for_handyman_profile(profile)
        return


async def handle_message(message: aio_pika.IncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body.decode("utf-8"))
            await process_event(payload)
        except Exception as e:
            headers_in = dict(message.headers or {})
            retry_count = int(headers_in.get("x-retry-count", 0) or 0)

            if retry_count >= MAX_RETRIES:
                print(f"[match-service] Poison message (DLQ): {e}")
                return

            headers_in["x-retry-count"] = retry_count + 1

            retry_msg = Message(
                body=message.body,
                headers=headers_in,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type=message.content_type or "application/json",
            )

            await message.channel.default_exchange.publish(retry_msg, routing_key=RETRY_QUEUE)
            print(f"[match-service] retry #{retry_count + 1}")


async def _connect_and_consume():
    connection = await connect()
    if connection is None:
        # events disabled
        return None

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=50)

    exchange = await declare_exchange(channel)

    main_queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": DLQ_QUEUE,
        },
    )

    await channel.declare_queue(
        RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": QUEUE_NAME,
        },
    )

    await channel.declare_queue(DLQ_QUEUE, durable=True)

    for rk in ROUTING_KEYS:
        await main_queue.bind(exchange, routing_key=rk)

    await main_queue.consume(handle_message)
    print("[match-service] consumer started with DLQ + retry")
    return connection


async def start_consumer_with_retry(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            conn = await _connect_and_consume()
            return conn  # can be None when events disabled
        except Exception as e:
            print(f"[match-service] consumer failed, retrying in {RETRY_SECONDS}s: {e}")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=RETRY_SECONDS)
            except asyncio.TimeoutError:
                continue