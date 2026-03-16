from __future__ import annotations

from shared.shared.outbox_worker import run_outbox_loop, make_outbox_stats
from .db import SessionLocal
from .models import OutboxEvent
from .messaging import publisher


async def outbox_stats() -> dict:
    return await make_outbox_stats(SessionLocal, OutboxEvent)


async def run_outbox_forever(stop_event):
    await run_outbox_loop(
        stop_event=stop_event,
        SessionLocal=SessionLocal,
        OutboxEvent=OutboxEvent,
        publisher=publisher,
        service_label="handyman-service",
        max_attempts=20,
    )
