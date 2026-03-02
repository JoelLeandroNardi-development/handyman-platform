import json
import aio_pika
from aio_pika import ExchangeType, Message
from dateutil import parser

from .rabbitmq import publisher
from .redis_client import redis_client
from .reservations import create_reservation, get_reservation, delete_reservation, overlaps
from .events import build_event, to_json

EXCHANGE_NAME = "domain_events"

QUEUE_NAME = "availability_service_booking_events"
RETRY_QUEUE = "availability_service_booking_events_retry"
DLQ_QUEUE = "availability_service_booking_events_dlq"

ROUTING_KEYS = [
    "booking.requested",
    "booking.confirm_requested",
    "booking.cancel_requested",
]

IDEMPOTENCY_TTL = 3600

MAX_RETRIES = 3
RETRY_DELAY_MS = 5000


def processed_key(event_id: str) -> str:
    return f"processed_event:{event_id}"


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

    new_slots = []
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

    pk = processed_key(event_id)
    if await redis_client.get(pk):
        return
    await redis_client.set(pk, "1", ex=IDEMPOTENCY_TTL)

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
            await publisher.publish("slot.rejected", to_json(ev))
            return

        ok = await create_reservation(booking_id, handyman_email, desired_start, desired_end)
        if ok:
            ev = build_event("slot.reserved", {"booking_id": booking_id})
            await publisher.publish("slot.reserved", to_json(ev))
        else:
            ev = build_event("slot.rejected", {"booking_id": booking_id, "reason": "slot_conflict_reserved"})
            await publisher.publish("slot.rejected", to_json(ev))
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
            await publisher.publish("slot.rejected", to_json(ev))
            return

        await apply_confirm_to_slots(handyman_email, desired_start, desired_end)
        await delete_reservation(booking_id)

        ev = build_event("slot.confirmed", {"booking_id": booking_id})
        await publisher.publish("slot.confirmed", to_json(ev))
        return

    if event_type == "booking.cancel_requested":
        booking_id = data.get("booking_id")
        if not booking_id:
            return

        # Release reservation (if it exists). If not exists, treat as idempotent success.
        await delete_reservation(booking_id)

        ev = build_event("slot.released", {"booking_id": booking_id})
        await publisher.publish("slot.released", to_json(ev))
        return


async def handle_message(message: aio_pika.IncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body.decode("utf-8"))
            await process_event(payload)
        except Exception as e:
            retry_count = int(message.headers.get("x-retry-count", 0) or 0)

            if retry_count >= MAX_RETRIES:
                print(f"[availability-service] Poison message (DLQ): {e}")
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

            print(f"[availability-service] retry #{retry_count + 1}")


async def start_consumer(rabbit_url: str):
    conn = await aio_pika.connect_robust(rabbit_url)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=50)

    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)

    main_queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": DLQ_QUEUE,
        },
    )

    await channel.declare_queue(
        RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": QUEUE_NAME,
        },
    )

    await channel.declare_queue(DLQ_QUEUE, durable=True)

    for rk in ROUTING_KEYS:
        await main_queue.bind(exchange, routing_key=rk)

    await main_queue.consume(handle_message)
    print("[availability-service] booking consumer started with DLQ + retry")
    return conn