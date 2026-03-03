from __future__ import annotations

import asyncio
import aio_pika

from shared.shared.consumer import run_consumer_with_retry_dlq
from shared.shared.idempotency import already_processed

from .services import (
    redis_client,
    invalidate_bucket,
    buckets_in_radius,
    fetch_handyman,
    norm,
)
from .messaging import connect, EXCHANGE_NAME

QUEUE_NAME = "match_service_domain_events"
RETRY_QUEUE = "match_service_domain_events_retry"
DLQ_QUEUE = "match_service_domain_events_dlq"

ROUTING_KEYS = [
    "availability.updated",
    "handyman.created",
    "handyman.location_updated",
]

MAX_RETRIES = 3
RETRY_DELAY_MS = 5000
IDEMPOTENCY_TTL_SECONDS = 3600
RETRY_SECONDS = 5


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

    if await already_processed(redis_client=redis_client, event_id=event_id, ttl_seconds=IDEMPOTENCY_TTL_SECONDS):
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


async def _connect_and_consume():
    connection = await connect()
    if connection is None:
        return None

    channel = await connection.channel()

    await run_consumer_with_retry_dlq(
        channel=channel,
        exchange_name=EXCHANGE_NAME,
        queue_name=QUEUE_NAME,
        retry_queue=RETRY_QUEUE,
        dlq_queue=DLQ_QUEUE,
        routing_keys=ROUTING_KEYS,
        handler=process_event,
        retry_delay_ms=RETRY_DELAY_MS,
        max_retries=MAX_RETRIES,
        prefetch=50,
        service_label="match-service",
    )

    print("[match-service] consumer started with DLQ + retry")
    return connection


async def start_consumer_with_retry(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            conn = await _connect_and_consume()
            return conn
        except Exception as e:
            print(f"[match-service] consumer failed, retrying in {RETRY_SECONDS}s: {e}")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=RETRY_SECONDS)
            except asyncio.TimeoutError:
                continue