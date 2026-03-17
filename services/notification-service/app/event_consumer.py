from __future__ import annotations

import asyncio
import time

import aio_pika

from shared.shared.consumer import run_consumer_with_retry_dlq

from .events import (
    ROUTING_KEYS,
    channels_for_event,
    extract_email_recipients,
    extract_push_targets,
    render_notification,
)
from .messaging import EXCHANGE_NAME, RABBIT_URL
from .providers import send_email, send_push


QUEUE_NAME = "notification_service_events"
RETRY_QUEUE = "notification_service_events_retry"
DLQ_QUEUE = "notification_service_events_dlq"

_IDEMPOTENCY_TTL_SECONDS = 3600
_seen_events: dict[str, float] = {}


def _prune_seen(now: float):
    expired = [key for key, ts in _seen_events.items() if now - ts > _IDEMPOTENCY_TTL_SECONDS]
    for key in expired:
        _seen_events.pop(key, None)


def _is_seen(event_id: str) -> bool:
    now = time.time()
    _prune_seen(now)
    return event_id in _seen_events


def _store_seen(event_id: str):
    _seen_events[event_id] = time.time()


async def process_event(payload: dict):
    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    data = payload.get("data") or {}

    if not event_id or not isinstance(event_id, str):
        return
    if event_type not in set(ROUTING_KEYS):
        return
    if _is_seen(event_id):
        return

    channels = channels_for_event(event_type)
    if not channels:
        return

    title, body = render_notification(event_type, data)

    if "email" in channels:
        for recipient in extract_email_recipients(data):
            await send_email(recipient, title, body, event_id, event_type)

    if "push" in channels:
        for topic in extract_push_targets(data):
            await send_push(topic, title, body, event_id, event_type)

    _store_seen(event_id)


async def start_consumer():
    if not RABBIT_URL:
        raise RuntimeError("RABBIT_URL is not set")

    conn = await aio_pika.connect_robust(RABBIT_URL)
    channel = await conn.channel()

    await run_consumer_with_retry_dlq(
        channel=channel,
        exchange_name=EXCHANGE_NAME,
        queue_name=QUEUE_NAME,
        retry_queue=RETRY_QUEUE,
        dlq_queue=DLQ_QUEUE,
        routing_keys=ROUTING_KEYS,
        handler=process_event,
        retry_delay_ms=5000,
        max_retries=3,
        prefetch=50,
        service_label="notification-service",
    )

    print("[notification-service] consumer started with DLQ + retry")
    return conn


async def start_consumer_with_retry(stop_event: asyncio.Event):
    if not RABBIT_URL:
        print("[notification-service] RABBIT_URL not set, consumer disabled")
        return None

    while not stop_event.is_set():
        try:
            return await start_consumer()
        except Exception as exc:
            print(f"[notification-service] consumer connect failed, retrying in 5s: {exc}")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5)
            except asyncio.TimeoutError:
                continue

    return None
