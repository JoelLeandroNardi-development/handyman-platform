from __future__ import annotations

import asyncio

from shared.shared.outbox_worker import run_outbox_loop, make_outbox_stats
from .db import SessionLocal
from .models import OutboxEvent
from .messaging import publisher


async def outbox_stats() -> dict:
    return await make_outbox_stats(SessionLocal, OutboxEvent)


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
        await run_outbox_loop(
            stop_event=self._stop,
            SessionLocal=SessionLocal,
            OutboxEvent=OutboxEvent,
            publisher=publisher,
            service_label="user-service",
            max_attempts=25,
        )


worker = OutboxWorker()
