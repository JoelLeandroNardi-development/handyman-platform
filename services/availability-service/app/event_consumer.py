import asyncio
import json
import aio_pika
from aio_pika import ExchangeType
from dateutil import parser

from .rabbitmq import publisher
from .redis_client import redis_client
from .reservations import create_reservation, get_reservation, delete_reservation, overlaps
from .events import build_event, to_json

EXCHANGE_NAME = "domain_events"
QUEUE_NAME = "availability_service_booking_events"
ROUTING_KEYS = ["booking.requested", "booking.confirm_requested"]

IDEMPOTENCY_TTL = 3600

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
    """
    Permanently consume desired window by removing/splitting overlapping slots.
    """
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

        # overlap => keep non-overlapping remainders
        if ss < ds:
            new_slots.append(f"{ss.isoformat()}|{ds.isoformat()}")
        if ee > de:
            new_slots.append(f"{de.isoformat()}|{ee.isoformat()}")

    await redis_client.delete(key)
    if new_slots:
        await redis_client.rpush(key, *new_slots)

async def handle_message(message: aio_pika.IncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except Exception:
            return

        event_id = payload.get("event_id")
        event_type = payload.get("event_type")
        data = payload.get("data") or {}

        if not event_id or not event_type:
            return

        # idempotent handling
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

            # must have a slot overlap in stored availability
            ok_slot = await handyman_has_slot(handyman_email, desired_start, desired_end)
            if not ok_slot:
                ev = build_event("slot.rejected", {"booking_id": booking_id, "reason": "no_matching_slot"})
                await publisher.publish("slot.rejected", to_json(ev))
                return

            # reserve with TTL (also checks conflicts vs existing reservations)
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
                # reservation missing => expired or never reserved
                ev = build_event("slot.rejected", {"booking_id": booking_id, "reason": "reservation_missing"})
                await publisher.publish("slot.rejected", to_json(ev))
                return

            # finalize: consume time from availability
            await apply_confirm_to_slots(handyman_email, desired_start, desired_end)
            await delete_reservation(booking_id)

            ev = build_event("slot.confirmed", {"booking_id": booking_id})
            await publisher.publish("slot.confirmed", to_json(ev))
            return

async def start_consumer(rabbit_url: str):
    conn = await aio_pika.connect_robust(rabbit_url)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=50)

    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)

    for rk in ROUTING_KEYS:
        await queue.bind(exchange, routing_key=rk)

    await queue.consume(handle_message)
    print("[availability-service] booking consumer started")
    return conn