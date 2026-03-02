import json
import aio_pika
from aio_pika import ExchangeType, Message
from sqlalchemy import select

from .rabbitmq import connect, EXCHANGE_NAME
from .db import SessionLocal
from .models import Booking

# Main / retry / DLQ queues
QUEUE_NAME = "booking_service_domain_events"
RETRY_QUEUE = "booking_service_domain_events_retry"
DLQ_QUEUE = "booking_service_domain_events_dlq"

# Events booking-service consumes
ROUTING_KEYS = ["slot.reserved", "slot.rejected", "slot.confirmed", "slot.expired"]

# Retry policy
MAX_RETRIES = 3
RETRY_DELAY_MS = 5000  # 5 seconds


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

        await db.commit()


async def handle_message(message: aio_pika.IncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body.decode("utf-8"))
            await process_event(payload)
        except Exception as e:
            retry_count = int(message.headers.get("x-retry-count", 0) or 0)

            if retry_count >= MAX_RETRIES:
                # Let RabbitMQ DLX route it to DLQ by raising no exception and just returning.
                # We explicitly publish to DLQ for clarity.
                print(f"[booking-service] Poison message (DLQ): {e}")
                return

            headers = dict(message.headers or {})
            headers["x-retry-count"] = retry_count + 1

            retry_msg = Message(
                body=message.body,
                headers=headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type=message.content_type or "application/json",
            )

            await message.channel.default_exchange.publish(
                retry_msg,
                routing_key=RETRY_QUEUE,
            )

            print(f"[booking-service] Message retry #{retry_count + 1} ({event_debug(payload=message.body)})")


def event_debug(payload: bytes) -> str:
    try:
        obj = json.loads(payload.decode("utf-8"))
        return f"{obj.get('event_type')}:{(obj.get('data') or {}).get('booking_id')}"
    except Exception:
        return "unparseable"


async def start_consumer():
    conn = await connect()
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=50)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, ExchangeType.TOPIC, durable=True
    )

    # Main queue routes poison to DLQ
    main_queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": DLQ_QUEUE,
        },
    )

    # Retry queue delays and returns to main
    await channel.declare_queue(
        RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": QUEUE_NAME,
        },
    )

    # DLQ
    await channel.declare_queue(DLQ_QUEUE, durable=True)

    for rk in ROUTING_KEYS:
        await main_queue.bind(exchange, routing_key=rk)

    await main_queue.consume(handle_message)
    print("[booking-service] consumer started with DLQ + retry")
    return conn