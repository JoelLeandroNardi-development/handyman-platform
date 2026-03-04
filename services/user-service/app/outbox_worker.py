from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal
from .models import OutboxEvent
from .messaging import publisher

POLL_INTERVAL_SECONDS = 1.0
BATCH_SIZE = 50
MAX_ATTEMPTS = 25


async def _claim_batch(db: AsyncSession):
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.status == "PENDING")
        .order_by(OutboxEvent.id.asc())
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def _mark_sent(db: AsyncSession, row_id: int):
    await db.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == row_id)
        .values(
            status="SENT",
            published_at=dt.datetime.now(dt.timezone.utc),
            last_error=None,
        )
    )


async def _mark_failure(db: AsyncSession, row_id: int, attempts: int, err: str):
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


async def outbox_stats() -> dict:
    async with SessionLocal() as db:
        res = await db.execute(select(OutboxEvent.status, func.count()).group_by(OutboxEvent.status))
        rows = res.all()

    counts = {status: int(n) for status, n in rows}
    return {
        "type": "sql",
        "pending": counts.get("PENDING", 0),
        "failed": counts.get("FAILED", 0),
        "sent": counts.get("SENT", 0),
    }


class OutboxWorker:
    def __init__(self):
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self):
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop.set()
        if self._task:
            try:
                await self._task
            except Exception:
                pass

    async def _run(self):
        await publisher.start()

        while not self._stop.is_set():
            try:
                async with SessionLocal() as db:
                    async with db.begin():
                        batch = await _claim_batch(db)
                        for ev in batch:
                            try:
                                await publisher.publish(
                                    routing_key=ev.routing_key,
                                    payload=ev.payload,
                                    message_id=ev.event_id,
                                )
                                await _mark_sent(db, ev.id)
                            except Exception as e:
                                next_attempts = (ev.attempts or 0) + 1
                                await _mark_failure(db, ev.id, next_attempts, str(e))
            except Exception as e:
                print(f"[user-service] outbox drain failed: {e}")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue


worker = OutboxWorker()