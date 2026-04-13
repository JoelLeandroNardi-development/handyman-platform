from __future__ import annotations

import asyncio

import aio_pika
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.constants import DataKey, EventType, NotificationType, PayloadKey
from .db import SessionLocal
from .config import (
    CONSUMER_RECONNECT_WAIT_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_PREFETCH,
    DEFAULT_RETRY_DELAY_MS,
    DLQ_QUEUE,
    EVENT_CONSUMER_ERROR,
    EVENT_CONSUMER_STARTED,
    EXCHANGE_NAME,
    QUEUE_NAME,
    RABBIT_URL,
    RETRY_QUEUE,
    SERVICE_NAME,
)
from .repository import create_notification_if_absent, get_preferences, unread_count
from ..api.sse import hub
from ..application.mappers import map_event_to_notifications
from ..application.preferences import category_enabled
from ..domain.schemas import NotificationItem
from shared.core.messaging.consumer import run_consumer_with_retry_dlq

ROUTING_KEYS = [
    EventType.BOOKING_REQUESTED,
    EventType.SLOT_RESERVED,
    EventType.SLOT_REJECTED,
    EventType.SLOT_CONFIRMED,
    EventType.SLOT_EXPIRED,
    EventType.SLOT_RELEASED,
    EventType.BOOKING_CANCEL_REQUESTED,
    EventType.BOOKING_COMPLETED,
    EventType.BOOKING_REJECTED,
    EventType.BOOKING_COMPLETED_BY_USER,
    EventType.BOOKING_COMPLETED_BY_HANDYMAN,
]

async def handle_event(db: AsyncSession, event: dict) -> None:
    intents = map_event_to_notifications(event)

    for intent in intents:
        pref = await get_preferences(db, user_email=intent[DataKey.USER_EMAIL])
        if not category_enabled(pref, intent["category"]):
            continue

        created = await create_notification_if_absent(db, **intent)
        if not created:
            continue

        count = await unread_count(db, user_email=intent[DataKey.USER_EMAIL])
        item = NotificationItem.model_validate(created)
        await hub.publish(
            intent[DataKey.USER_EMAIL],
            {
                PayloadKey.TYPE: NotificationType.NOTIFICATION_CREATED,
                PayloadKey.NOTIFICATION: item.model_dump(mode="json"),
                PayloadKey.UNREAD_COUNT: count,
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
        retry_delay_ms=DEFAULT_RETRY_DELAY_MS,
        max_retries=DEFAULT_MAX_RETRIES,
        prefetch=DEFAULT_PREFETCH,
        service_label=SERVICE_NAME,
    )

    print({"service": SERVICE_NAME, "event": EVENT_CONSUMER_STARTED})
    return connection

async def consume_forever(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        connection = None
        try:
            connection = await start_consumer()
            await stop_event.wait()
        except Exception as exc:
            print({"service": SERVICE_NAME, "event": EVENT_CONSUMER_ERROR, "error": str(exc)})
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=CONSUMER_RECONNECT_WAIT_SECONDS)
            except asyncio.TimeoutError:
                pass
        finally:
            try:
                if connection and not connection.is_closed:
                    await connection.close()
            except Exception:
                pass