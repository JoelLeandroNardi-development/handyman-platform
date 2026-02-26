import asyncio
import time

from .redis_client import redis_client
from .reservations import delete_reservation
from .events import build_event, to_json
from .rabbitmq import publisher

EXPIRY_ZSET = "reservation_expiry"

async def expiry_loop(stop_event: asyncio.Event):
    while not stop_event.is_set():
        now = time.time()
        # pop up to N expired per tick
        expired = await redis_client.zrangebyscore(EXPIRY_ZSET, 0, now, start=0, num=50)
        if expired:
            for booking_id in expired:
                await redis_client.zrem(EXPIRY_ZSET, booking_id)
                # delete reservation key + handyman index
                await delete_reservation(booking_id)
                ev = build_event("slot.expired", {"booking_id": booking_id})
                await publisher.publish("slot.expired", to_json(ev))
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            continue