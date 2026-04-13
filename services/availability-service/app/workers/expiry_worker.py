import asyncio
import time

from ..domain.constants import DataKey, EXPIRY_ZSET, SlotEventType
from ..domain.events import build_event
from ..infrastructure.config import EXPIRY_BATCH_SIZE, EXPIRY_POLL_INTERVAL_SECONDS
from ..infrastructure.cache import redis_client
from ..infrastructure.outbox_worker import enqueue_domain_event
from ..infrastructure.repository import delete_reservation, get_reservation

async def expiry_loop(stop_event: asyncio.Event):
    while not stop_event.is_set():
        now = time.time()
        expired = await redis_client.zrangebyscore(
            EXPIRY_ZSET,
            0,
            now,
            start=0,
            num=EXPIRY_BATCH_SIZE,
        )

        if expired:
            for booking_id in expired:
                await redis_client.zrem(EXPIRY_ZSET, booking_id)
                reservation = await get_reservation(booking_id)
                await delete_reservation(booking_id)

                ev = build_event(
                    SlotEventType.EXPIRED,
                    {
                        DataKey.BOOKING_ID: booking_id,
                        DataKey.USER_EMAIL: (reservation or {}).get(DataKey.USER_EMAIL),
                        DataKey.HANDYMAN_EMAIL: (reservation or {}).get(DataKey.HANDYMAN_EMAIL),
                    },
                )
                await enqueue_domain_event(ev)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=EXPIRY_POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue