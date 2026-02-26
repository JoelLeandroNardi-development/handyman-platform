import json
import aio_pika
from sqlalchemy import select

from .rabbitmq import connect, EXCHANGE_NAME
from .db import SessionLocal
from .models import Booking

QUEUE_NAME = "booking_service_domain_events"
ROUTING_KEYS = ["slot.reserved", "slot.rejected", "slot.confirmed", "slot.expired"]

async def handle_message(message: aio_pika.IncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except Exception:
            return

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

            await db.commit()

async def start_consumer():
    conn = await connect()
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=50)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )

    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    for rk in ROUTING_KEYS:
        await queue.bind(exchange, routing_key=rk)

    await queue.consume(handle_message)
    print("[booking-service] consumer started")
    return conn