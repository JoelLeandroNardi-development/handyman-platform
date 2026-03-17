from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .event_consumer import DLQ_QUEUE, QUEUE_NAME, RETRY_QUEUE, ROUTING_KEYS, start_consumer_with_retry
from .messaging import EXCHANGE_NAME, RABBIT_URL
from .providers import providers_config, recent_count, recent_notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    consumer_task: asyncio.Task | None = None
    consumer_conn = None

    async def run_consumer():
        nonlocal consumer_conn
        consumer_conn = await start_consumer_with_retry(stop_event)

    consumer_task = asyncio.create_task(run_consumer())

    try:
        yield
    finally:
        stop_event.set()

        try:
            if consumer_task:
                await consumer_task
        except Exception:
            pass

        try:
            if consumer_conn and not consumer_conn.is_closed:
                await consumer_conn.close()
        except Exception:
            pass


app = FastAPI(title="Notification Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "notification-service",
        "events_enabled": bool(RABBIT_URL),
        "exchange_name": EXCHANGE_NAME,
        "rabbit_url_set": bool(RABBIT_URL),
        "recent_notifications": recent_count(),
    }


@app.get("/debug/rabbit")
async def debug_rabbit():
    return {
        "service": "notification-service",
        "rabbit_url_set": bool(RABBIT_URL),
        "exchange_name": EXCHANGE_NAME,
        "consumer": {
            "queue_name": QUEUE_NAME,
            "retry_queue": RETRY_QUEUE,
            "dlq_queue": DLQ_QUEUE,
            "routing_keys": ROUTING_KEYS,
        },
    }


@app.get("/debug/notifications")
async def debug_notifications(limit: int = 20):
    clamped = max(1, min(limit, 200))
    return {
        "service": "notification-service",
        "count": recent_count(),
        "items": recent_notifications(limit=clamped),
    }


@app.get("/debug/providers")
async def debug_providers():
    return {
        "service": "notification-service",
        "providers": providers_config(),
    }
