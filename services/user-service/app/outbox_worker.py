import asyncio
from sqlalchemy import select
from sqlalchemy.sql import func

from .db import SessionLocal
from .models import OutboxEvent
from .messaging import publisher

POLL_INTERVAL_SECONDS = 1.0
BATCH_SIZE = 50
MAX_ATTEMPTS = 25


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
        while not self._stop.is_set():
            try:
                await self._drain_once()
            except Exception as e:
                print(f"[user-service] outbox drain failed: {e}")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue

    async def _drain_once(self):
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
                    await publisher.publish(ev.routing_key, ev.payload)
                    ev.status = "SENT"
                    ev.published_at = func.now()
                except Exception as e:
                    ev.attempts += 1
                    ev.last_error = str(e)

            await db.commit()


worker = OutboxWorker()