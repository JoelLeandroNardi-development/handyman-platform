from __future__ import annotations

from dateutil import parser
import aio_pika

from shared.shared.consumer import run_consumer_with_retry_dlq
from shared.shared.idempotency import already_processed

from .redis_client import redis_client
from .reservations import create_reservation, get_reservation, delete_reservation, overlaps
from .events import build_event
from .outbox_worker import enqueue_domain_event
from .messaging import RABBIT_URL, EXCHANGE_NAME

QUEUE_NAME = "availability_service_booking_events"
RETRY_QUEUE = "availability_service_booking_events_retry"
DLQ_QUEUE = "availability_service_booking_events_dlq"

ROUTING_KEYS = [
    "booking.requested",
    "booking.confirm_requested",
    "booking.cancel_requested",
]

IDEMPOTENCY_TTL = 3600


def avail_key(email: str) -> str:
    return f"availability:{email}"


def parse(dt: str):
    return parser.isoparse(dt)


async def handyman_has_slot(email: str, desired_start: str, desired_end: str) -> bool:
    ds = parse(desired_start)
    de = parse(desired_end)

    slots = await redis_client.lrange(avail_key(email), 0, -1)
    for slot in slots:
        try:
            s, e = slot.split("|")
            ss = parse(s)
            ee = parse(e)
        except Exception:
            continue

        if overlaps(ss, ee, ds, de):
            return True
    return False


async def apply_confirm_to_slots(email: str, desired_start: str, desired_end: str):
    ds = parse(desired_start)
    de = parse(desired_end)

    key = avail_key(email)
    slots = await redis_client.lrange(key, 0, -1)

    new_slots: list[str] = []
    for slot in slots:
        try:
            s, e = slot.split("|")
            ss = parse(s)
            ee = parse(e)
        except Exception:
            continue

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

    if await already_processed(redis_client=redis_client, event_id=event_id, ttl_seconds=IDEMPOTENCY_TTL):
        return

    if event_type == "booking.requested":
        booking_id = data.get("booking_id")
        handyman_email = data.get("handyman_email")
        desired_start = data.get("desired_start")
        desired_end = data.get("desired_end")

        if not all([booking_id, handyman_email, desired_start, desired_end]):
            return

        ok_slot = await handyman_has_slot(handyman_email, desired_start, desired_end)
        if not ok_slot:
            ev = build_event("slot.rejected", {"booking_id": booking_id, "reason": "no_matching_slot"})
            await enqueue_domain_event(ev)
            return

        ok = await create_reservation(booking_id, handyman_email, desired_start, desired_end)
        if ok:
            ev = build_event("slot.reserved", {"booking_id": booking_id})
            await enqueue_domain_event(ev)
        else:
            ev = build_event("slot.rejected", {"booking_id": booking_id, "reason": "slot_conflict_reserved"})
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
            ev = build_event("slot.rejected", {"booking_id": booking_id, "reason": "reservation_missing"})
            await enqueue_domain_event(ev)
            return

        await apply_confirm_to_slots(handyman_email, desired_start, desired_end)
        await delete_reservation(booking_id)

        ev = build_event("slot.confirmed", {"booking_id": booking_id})
        await enqueue_domain_event(ev)
        return

    if event_type == "booking.cancel_requested":
        booking_id = data.get("booking_id")
        if not booking_id:
            return

        await delete_reservation(booking_id)

        ev = build_event("slot.released", {"booking_id": booking_id})
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