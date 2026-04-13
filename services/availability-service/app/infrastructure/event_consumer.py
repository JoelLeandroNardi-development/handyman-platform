from __future__ import annotations

from dateutil import parser
import aio_pika

from .config import (
    DEFAULT_MAX_RETRIES, DEFAULT_PREFETCH, DEFAULT_RETRY_DELAY_MS, DLQ_QUEUE,
    IDEMPOTENCY_TTL_SECONDS, QUEUE_NAME, RABBIT_URL_MISSING_ERROR, RETRY_QUEUE,
    ROUTING_KEYS, SERVICE_LOG_PREFIX, SERVICE_NAME,
)
from .cache import redis_client
from .messaging import RABBIT_URL, EXCHANGE_NAME
from .outbox_worker import enqueue_domain_event
from .repository import create_reservation, get_reservation, delete_reservation
from ..application.helpers import avail_key, parse_raw_slot
from ..domain.constants import (
    AvailabilityEventType, BookingEventType, DataKey,
    EventKey, RejectionReason, SlotEventType,
)
from ..domain.events import build_event
from shared.core.messaging.consumer import run_consumer_with_retry_dlq
from shared.core.utils.idempotency import already_processed
from shared.core.utils.intervals import fully_contains as contains_interval, overlaps

async def read_current_slots(email: str) -> list[dict]:
    slots = await redis_client.lrange(avail_key(email), 0, -1)

    parsed: list[dict] = []
    for slot in slots or []:
        result = parse_raw_slot(slot)
        if result is None:
            continue
        ss, ee = result
        parsed.append({DataKey.START: ss.isoformat(), DataKey.END: ee.isoformat()})

    return parsed

async def emit_availability_updated(email: str) -> None:
    ev = build_event(
        AvailabilityEventType.UPDATED,
        {
            DataKey.EMAIL: email,
            DataKey.SLOTS: await read_current_slots(email),
        },
    )
    await enqueue_domain_event(ev)

async def handyman_has_slot(email: str, desired_start: str, desired_end: str) -> bool:
    ds = parser.isoparse(desired_start)
    de = parser.isoparse(desired_end)

    if de <= ds:
        return False

    slots = await redis_client.lrange(avail_key(email), 0, -1)
    for slot in slots:
        result = parse_raw_slot(slot)
        if result is None:
            continue
        ss, ee = result
        if contains_interval(ss, ee, ds, de):
            return True

    return False

async def apply_confirm_to_slots(email: str, desired_start: str, desired_end: str):
    ds = parser.isoparse(desired_start)
    de = parser.isoparse(desired_end)

    key = avail_key(email)
    slots = await redis_client.lrange(key, 0, -1)

    new_slots: list[str] = []
    for slot in slots:
        result = parse_raw_slot(slot)
        if result is None:
            continue
        ss, ee = result

        if not overlaps(ss, ee, ds, de):
            new_slots.append(f"{ss.isoformat()}|{ee.isoformat()}")
            continue

        if ss < ds:
            new_slots.append(f"{ss.isoformat()}|{ds.isoformat()}")
        if ee > de:
            new_slots.append(f"{de.isoformat()}|{ee.isoformat()}")

    await redis_client.delete(key)
    if new_slots:
        await redis_client.rpush(key, *new_slots)

async def process_event(payload: dict):
    event_id = payload.get("event_id")
    event_type = payload.get(EventKey.EVENT_TYPE)
    data = payload.get(EventKey.DATA) or {}

    if not event_id or not event_type:
        return
    if event_type not in ROUTING_KEYS:
        return

    if await already_processed(
        redis_client=redis_client,
        event_id=event_id,
        ttl_seconds=IDEMPOTENCY_TTL_SECONDS,
    ):
        return

    if event_type == BookingEventType.REQUESTED:
        booking_id = data.get(DataKey.BOOKING_ID)
        user_email = data.get(DataKey.USER_EMAIL)
        handyman_email = data.get(DataKey.HANDYMAN_EMAIL)
        desired_start = data.get(DataKey.DESIRED_START)
        desired_end = data.get(DataKey.DESIRED_END)

        if not all([booking_id, user_email, handyman_email, desired_start, desired_end]):
            return

        ok_slot = await handyman_has_slot(handyman_email, desired_start, desired_end)
        if not ok_slot:
            ev = build_event(
                SlotEventType.REJECTED,
                {
                    DataKey.BOOKING_ID: booking_id,
                    DataKey.USER_EMAIL: user_email,
                    DataKey.HANDYMAN_EMAIL: handyman_email,
                    DataKey.REASON: RejectionReason.NO_MATCHING_SLOT,
                },
            )
            await enqueue_domain_event(ev)
            return

        ok = await create_reservation(
            booking_id,
            user_email,
            handyman_email,
            desired_start,
            desired_end,
        )
        if ok:
            ev = build_event(
                SlotEventType.RESERVED,
                {
                    DataKey.BOOKING_ID: booking_id,
                    DataKey.USER_EMAIL: user_email,
                    DataKey.HANDYMAN_EMAIL: handyman_email,
                },
            )
            await enqueue_domain_event(ev)
        else:
            ev = build_event(
                SlotEventType.REJECTED,
                {
                    DataKey.BOOKING_ID: booking_id,
                    DataKey.USER_EMAIL: user_email,
                    DataKey.HANDYMAN_EMAIL: handyman_email,
                    DataKey.REASON: RejectionReason.SLOT_CONFLICT_RESERVED,
                },
            )
            await enqueue_domain_event(ev)
        return

    if event_type == BookingEventType.CONFIRM_REQUESTED:
        booking_id = data.get(DataKey.BOOKING_ID)
        handyman_email = data.get(DataKey.HANDYMAN_EMAIL)
        desired_start = data.get(DataKey.DESIRED_START)
        desired_end = data.get(DataKey.DESIRED_END)

        if not all([booking_id, handyman_email, desired_start, desired_end]):
            return

        res = await get_reservation(booking_id)
        if not res:
            ev = build_event(
                SlotEventType.REJECTED,
                {
                    DataKey.BOOKING_ID: booking_id,
                    DataKey.USER_EMAIL: data.get(DataKey.USER_EMAIL),
                    DataKey.HANDYMAN_EMAIL: handyman_email,
                    DataKey.REASON: RejectionReason.RESERVATION_MISSING,
                },
            )
            await enqueue_domain_event(ev)
            return

        await apply_confirm_to_slots(handyman_email, desired_start, desired_end)
        await delete_reservation(booking_id)
        await emit_availability_updated(handyman_email)

        ev = build_event(
            SlotEventType.CONFIRMED,
            {
                DataKey.BOOKING_ID: booking_id,
                DataKey.USER_EMAIL: res.get(DataKey.USER_EMAIL) or data.get(DataKey.USER_EMAIL),
                DataKey.HANDYMAN_EMAIL: res.get(DataKey.HANDYMAN_EMAIL) or handyman_email,
            },
        )
        await enqueue_domain_event(ev)
        return

    if event_type == BookingEventType.CANCEL_REQUESTED:
        booking_id = data.get(DataKey.BOOKING_ID)
        if not booking_id:
            return

        res = await get_reservation(booking_id)
        await delete_reservation(booking_id)

        ev = build_event(
            SlotEventType.RELEASED,
            {
                DataKey.BOOKING_ID: booking_id,
                DataKey.USER_EMAIL: data.get(DataKey.USER_EMAIL) or (res or {}).get(DataKey.USER_EMAIL),
                DataKey.HANDYMAN_EMAIL: data.get(DataKey.HANDYMAN_EMAIL) or (res or {}).get(DataKey.HANDYMAN_EMAIL),
                DataKey.REASON: data.get(DataKey.REASON),
            },
        )
        await enqueue_domain_event(ev)
        return

async def start_consumer():
    if not RABBIT_URL:
        raise RuntimeError(RABBIT_URL_MISSING_ERROR)

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
        retry_delay_ms=DEFAULT_RETRY_DELAY_MS,
        max_retries=DEFAULT_MAX_RETRIES,
        prefetch=DEFAULT_PREFETCH,
        service_label=SERVICE_NAME,
    )

    print(f"{SERVICE_LOG_PREFIX} booking consumer started with DLQ + retry")
    return conn