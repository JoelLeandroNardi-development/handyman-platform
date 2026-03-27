from __future__ import annotations

from ..domain.models import OutboxEvent
from ..infrastructure.db import SessionLocal
from ..infrastructure.messaging import publisher
from shared.shared.outbox_worker import run_outbox_loop, make_outbox_stats

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