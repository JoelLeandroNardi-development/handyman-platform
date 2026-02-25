import asyncio
import json
import aio_pika
from aio_pika import ExchangeType

from .rabbitmq import connect, EXCHANGE_NAME
from .services import (
    redis_client,
    invalidate_bucket,
    buckets_in_radius,
    fetch_handyman,
    norm,
)

QUEUE_NAME = "match_service_domain_events"

ROUTING_KEYS = [
    "availability.updated",
    "handyman.created",
    "handyman.location_updated",
    "user.created",
    "user.location_updated",
]

IDEMPOTENCY_TTL_SECONDS = 60 * 60  # 1 hour
RETRY_SECONDS = 5


async def _already_processed(event_id: str) -> bool:
    key = f"processed_event:{event_id}"
    exists = await redis_client.get(key)
    if exists:
        return True
    await redis_client.set(key, "1", ex=IDEMPOTENCY_TTL_SECONDS)
    return False


async def _invalidate_for_handyman_profile(profile: dict):
    """
    profile needs:
      - skills: list[str]
      - latitude/longitude
      - service_radius_km
    Invalidate both strict and degraded caches conservatively.
    """
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

    # delete both modes for each skill/bucket
    for skill in skills:
        for mode in ("strict", "degraded"):
            for b_lat, b_lon in buckets:
                await invalidate_bucket(mode, skill, b_lat, b_lon)


async def handle_message(message: aio_pika.IncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except Exception:
            return

        event_id = payload.get("event_id")
        event_type = payload.get("event_type")
        data = payload.get("data") or {}

        if not event_id or not event_type:
            return

        if event_type not in set(ROUTING_KEYS):
            return

        if await _already_processed(event_id):
            return

        # ---- Availability: fetch handyman profile for precise invalidation ----
        if event_type == "availability.updated":
            email = data.get("email")
            if not email:
                return
            profile = await fetch_handyman(email)
            await _invalidate_for_handyman_profile(profile)
            return

        # ---- Handyman created: use event payload directly if complete ----
        if event_type == "handyman.created":
            await _invalidate_for_handyman_profile(data)
            return

        # ---- Handyman location updated: event may not include skills/radius; fetch profile ----
        if event_type == "handyman.location_updated":
            email = data.get("email")
            if not email:
                return
            profile = await fetch_handyman(email)
            await _invalidate_for_handyman_profile(profile)
            return

        # ---- User events: no invalidation needed (new location => different cache key) ----
        return


async def _connect_and_consume():
    connection = await connect()
    if connection is None:
        raise RuntimeError("RABBIT_URL not set; cannot start consumer")

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

    for rk in ROUTING_KEYS:
        await queue.bind(exchange, routing_key=rk)

    await queue.consume(handle_message)

    print("[match-service] event consumer started (surgical invalidation)")
    return connection


async def start_consumer_with_retry(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            conn = await _connect_and_consume()
            return conn
        except Exception as e:
            print(f"[match-service] consumer connect failed, retrying in {RETRY_SECONDS}s: {e}")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=RETRY_SECONDS)
            except asyncio.TimeoutError:
                continue

    return None
