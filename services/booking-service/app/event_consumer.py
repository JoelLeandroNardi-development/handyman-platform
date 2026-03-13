from __future__ import annotations

from sqlalchemy import select
import aio_pika

from shared.shared.consumer import run_consumer_with_retry_dlq

from .db import SessionLocal
from .models import Booking
from .messaging import EXCHANGE_NAME, RABBIT_URL, publisher

QUEUE_NAME = "booking_service_domain_events"
RETRY_QUEUE = "booking_service_domain_events_retry"
DLQ_QUEUE = "booking_service_domain_events_dlq"

ROUTING_KEYS = [
    "slot.reserved",
    "slot.rejected",
    "slot.confirmed",
    "slot.expired",
    "slot.released",
]


async def process_event(payload: dict):
    event_type = payload.get("event_type")
    data = payload.get("data") or {}
    booking_id = data.get("booking_id")

    if event_type not in set(ROUTING_KEYS) or not booking_id:
        return

    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()
        if not booking:
            return

        if event_type == "slot.reserved":
            if booking.status == "PENDING":
                booking.status = "RESERVED"

        elif event_type == "slot.rejected":
            if booking.status in ("PENDING", "RESERVED"):
                booking.status = "FAILED"
                booking.failure_reason = data.get("reason") or "slot_rejected"

        elif event_type == "slot.confirmed":
            if booking.status == "RESERVED":
                booking.status = "CONFIRMED"

        elif event_type == "slot.expired":
            if booking.status in ("PENDING", "RESERVED"):
                booking.status = "EXPIRED"

        elif event_type == "slot.released":
            if booking.status not in ("CANCELED", "REJECTED"):
                booking.status = "CANCELED"
                booking.cancellation_reason = booking.cancellation_reason or "released"

        await db.commit()


async def start_consumer():
    if not RABBIT_URL:
        raise RuntimeError("RABBIT_URL environment variable is not set")

    await publisher.start()

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
        service_label="booking-service",
    )

    print("[booking-service] consumer started with DLQ + retry")
    return conn