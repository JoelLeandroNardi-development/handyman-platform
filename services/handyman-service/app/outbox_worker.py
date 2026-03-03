import asyncio
from sqlalchemy import select
from sqlalchemy.sql import func

from .db import SessionLocal
from .models import OutboxEvent
from .messaging import mq

POLL_INTERVAL_SECONDS = 1.0
BATCH_SIZE = 50
MAX_ATTEMPTS = 20


async def drain_outbox_once():
    async with SessionLocal() as db:
        res = await db.execute(
            select(OutboxEvent)
            .where(OutboxEvent.status == "PENDING")
            .order_by(OutboxEvent.id.asc())
            .limit(BATCH_SIZE)
        )
        events = res.scalars().all()

        if not events:
            return

        for ev in events:
            if ev.attempts >= MAX_ATTEMPTS:
                ev.status = "FAILED"
                ev.last_error = "max_attempts_exceeded"
                continue

            try:
                await mq.publish(ev.routing_key, ev.payload)
                ev.status = "SENT"
                ev.published_at = func.now()
            except Exception as e:
                ev.attempts += 1
                ev.last_error = str(e)

        await db.commit()


async def run_outbox_forever(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await drain_outbox_once()
        except Exception as e:
            print(f"[handyman-service] outbox drain failed: {e}")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue