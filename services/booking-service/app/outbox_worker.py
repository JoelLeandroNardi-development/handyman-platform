import asyncio
import datetime as dt
import os
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal
from .models import OutboxEvent
from .messaging import mq

POLL_INTERVAL_SECONDS = float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "1.0"))
BATCH_SIZE = int(os.getenv("OUTBOX_BATCH_SIZE", "50"))
MAX_ATTEMPTS = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "20"))


async def _claim_batch(db: AsyncSession) -> Sequence[OutboxEvent]:
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.status == "PENDING")
        .order_by(OutboxEvent.id.asc())
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def _mark_sent(db: AsyncSession, row_id: int) -> None:
    await db.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == row_id)
        .values(
            status="SENT",
            published_at=dt.datetime.now(dt.timezone.utc),
            last_error=None,
        )
    )


async def _mark_failure(db: AsyncSession, row_id: int, attempts: int, err: str) -> None:
    new_status = "FAILED" if attempts >= MAX_ATTEMPTS else "PENDING"
    await db.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == row_id)
        .values(
            status=new_status,
            attempts=attempts,
            last_error=(err or "")[:500],
        )
    )


async def run_outbox_forever(stop_event: asyncio.Event) -> None:
    # ensure connection established
    await mq.connect()

    while not stop_event.is_set():
        try:
            async with SessionLocal() as db:
                async with db.begin():
                    batch = await _claim_batch(db)

                    for ev in batch:
                        try:
                            await mq.publish_json(
                                routing_key=ev.routing_key,
                                payload=ev.payload,
                                message_id=ev.event_id,
                            )
                            await _mark_sent(db, ev.id)
                        except Exception as e:
                            next_attempts = (ev.attempts or 0) + 1
                            await _mark_failure(db, ev.id, next_attempts, str(e))

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[booking-service] outbox worker error: {e}")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                continue