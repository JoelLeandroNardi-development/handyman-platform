from __future__ import annotations

import asyncio
import os

import aio_pika
from sqlalchemy.ext.asyncio import AsyncSession

from shared.shared.consumer import run_consumer_with_retry_dlq

from .db import SessionLocal
from .mapper import map_event_to_notifications
from .preferences import category_enabled
from .repository import create_notification_if_absent, get_preferences, unread_count
from .sse import hub
from .schemas import NotificationItem

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE_NAME = os.getenv("DOMAIN_EVENTS_EXCHANGE", "domain_events")
QUEUE_NAME = os.getenv("NOTIFICATION_QUEUE", "notification_service_events")
RETRY_QUEUE = f"{QUEUE_NAME}_retry"
DLQ_QUEUE = f"{QUEUE_NAME}_dlq"

ROUTING_KEYS = [
    "booking.requested",
    "slot.reserved",
    "slot.rejected",
    "slot.confirmed",
    "slot.expired",
    "slot.released",
    "booking.cancel_requested",
    "booking.completed",
    "booking.rejected",
    "booking.completed_by_user",
    "booking.completed_by_handyman",
]


async def handle_event(db: AsyncSession, event: dict) -> None:
    intents = map_event_to_notifications(event)

    for intent in intents:
        pref = await get_preferences(db, user_email=intent["user_email"])
        if not category_enabled(pref, intent["category"]):
            continue

        created = await create_notification_if_absent(db, **intent)
        if not created:
            continue

        count = await unread_count(db, user_email=intent["user_email"])
        item = NotificationItem.model_validate(created)
        await hub.publish(
            intent["user_email"],
            {
                "type": "notification.created",
                "notification": item.model_dump(mode="json"),
                "unread_count": count,
            },
        )


async def _process_event(payload: dict) -> None:
    async with SessionLocal() as db:
        await handle_event(db, payload)


async def start_consumer() -> aio_pika.abc.AbstractRobustConnection:
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()

    await run_consumer_with_retry_dlq(
        channel=channel,
        exchange_name=EXCHANGE_NAME,
        queue_name=QUEUE_NAME,
        retry_queue=RETRY_QUEUE,
        dlq_queue=DLQ_QUEUE,
        routing_keys=ROUTING_KEYS,
        handler=_process_event,
        retry_delay_ms=5000,
        max_retries=3,
        prefetch=100,
        service_label="notification-service",
    )

    print("[notification-service] consumer started")
    return connection


async def consume_forever(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        connection = None
        try:
            connection = await start_consumer()
            await stop_event.wait()
        except Exception as exc:
            print({"service": "notification-service", "event": "consumer_error", "error": str(exc)})
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
        finally:
            try:
                if connection and not connection.is_closed:
                    await connection.close()
            except Exception:
                pass
