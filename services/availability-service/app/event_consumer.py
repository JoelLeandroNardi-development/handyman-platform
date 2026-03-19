from __future__ import annotations

from dateutil import parser
import aio_pika

from shared.shared.consumer import run_consumer_with_retry_dlq
from shared.shared.idempotency import already_processed
from shared.shared.intervals import fully_contains as contains_interval, overlaps

from .redis_client import redis_client
from .reservations import create_reservation, get_reservation, delete_reservation
from .events import build_event
from .outbox_worker import enqueue_domain_event
from .messaging import RABBIT_URL, EXCHANGE_NAME
from .slot_helpers import avail_key, parse_raw_slot

QUEUE_NAME = "availability_service_booking_events"
RETRY_QUEUE = "availability_service_booking_events_retry"
DLQ_QUEUE = "availability_service_booking_events_dlq"

ROUTING_KEYS = [
    "booking.requested",
    "booking.confirm_requested",
    "booking.cancel_requested",
]

IDEMPOTENCY_TTL = 3600


async def read_current_slots(email: str) -> list[dict]:
    slots = await redis_client.lrange(avail_key(email), 0, -1)

    parsed: list[dict] = []
    for slot in slots or []:
        result = parse_raw_slot(slot)
        if result is None:
            continue
        ss, ee = result
        parsed.append({"start": ss.isoformat(), "end": ee.isoformat()})

    return parsed


async def emit_availability_updated(email: str) -> None:
    ev = build_event(
        "availability.updated",
        {
            "email": email,
            "slots": await read_current_slots(email),
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
    event_type = payload.get("event_type")
    data = payload.get("data") or {}

    if not event_id or not event_type:
        return
    if event_type not in set(ROUTING_KEYS):
        return

    if await already_processed(
        redis_client=redis_client,
        event_id=event_id,
        ttl_seconds=IDEMPOTENCY_TTL,
    ):
        return

    if event_type == "booking.requested":
        booking_id = data.get("booking_id")
        user_email = data.get("user_email")
        handyman_email = data.get("handyman_email")
        desired_start = data.get("desired_start")
        desired_end = data.get("desired_end")

        if not all([booking_id, user_email, handyman_email, desired_start, desired_end]):
            return

        ok_slot = await handyman_has_slot(handyman_email, desired_start, desired_end)
        if not ok_slot:
            ev = build_event(
                "slot.rejected",
                {
                    "booking_id": booking_id,
                    "user_email": user_email,
                    "handyman_email": handyman_email,
                    "reason": "no_matching_slot",
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
                "slot.reserved",
                {
                    "booking_id": booking_id,
                    "user_email": user_email,
                    "handyman_email": handyman_email,
                },
            )
            await enqueue_domain_event(ev)
        else:
            ev = build_event(
                "slot.rejected",
                {
                    "booking_id": booking_id,
                    "user_email": user_email,
                    "handyman_email": handyman_email,
                    "reason": "slot_conflict_reserved",
                },
            )
            await enqueue_domain_event(ev)
        return

    if event_type == "booking.confirm_requested":
        booking_id = data.get("booking_id")
        handyman_email = data.get("handyman_email")
        desired_start = data.get("desired_start")
        desired_end = data.get("desired_end")

        if not all([booking_id, handyman_email, desired_start, desired_end]):
            return

        res = await get_reservation(booking_id)
        if not res:
            ev = build_event(
                "slot.rejected",
                {
                    "booking_id": booking_id,
                    "user_email": data.get("user_email"),
                    "handyman_email": handyman_email,
                    "reason": "reservation_missing",
                },
            )
            await enqueue_domain_event(ev)
            return

        await apply_confirm_to_slots(handyman_email, desired_start, desired_end)
        await delete_reservation(booking_id)
        await emit_availability_updated(handyman_email)

        ev = build_event(
            "slot.confirmed",
            {
                "booking_id": booking_id,
                "user_email": res.get("user_email") or data.get("user_email"),
                "handyman_email": res.get("handyman_email") or handyman_email,
            },
        )
        await enqueue_domain_event(ev)
        return

    if event_type == "booking.cancel_requested":
        booking_id = data.get("booking_id")
        if not booking_id:
            return

        res = await get_reservation(booking_id)
        await delete_reservation(booking_id)

        ev = build_event(
            "slot.released",
            {
                "booking_id": booking_id,
                "user_email": data.get("user_email") or (res or {}).get("user_email"),
                "handyman_email": data.get("handyman_email") or (res or {}).get("handyman_email"),
                "reason": data.get("reason"),
            },
        )
        await enqueue_domain_event(ev)
        return


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
        service_label="availability-service",
    )

    print("[availability-service] booking consumer started with DLQ + retry")
    return conn