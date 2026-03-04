from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routes import router
from .event_consumer import start_consumer, QUEUE_NAME, ROUTING_KEYS
from .outbox_worker import run_outbox_forever, outbox_stats
from .messaging import publisher, RABBIT_URL, EXCHANGE_NAME


_stop = asyncio.Event()
_consumer_conn = None
_outbox_task: asyncio.Task | None = None
_consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_conn, _outbox_task, _consumer_task

    print("[booking-service] starting up...")

    try:
        await publisher.start()
    except Exception as e:
        print(f"[booking-service] publisher start failed (ok): {type(e).__name__}: {e}")

    _outbox_task = asyncio.create_task(run_outbox_forever(_stop))

    async def consumer_with_retry():
        global _consumer_conn
        while not _stop.is_set():
            try:
                _consumer_conn = await start_consumer()
                return
            except Exception as e:
                print(f"[booking-service] consumer connect failed, retrying in 5s: {e}")
                try:
                    await asyncio.wait_for(_stop.wait(), timeout=5)
                except asyncio.TimeoutError:
                    continue

    _consumer_task = asyncio.create_task(consumer_with_retry())

    yield

    print("[booking-service] shutting down...")
    _stop.set()

    if _outbox_task:
        _outbox_task.cancel()

    if _consumer_task:
        _consumer_task.cancel()

    try:
        if _consumer_conn and not _consumer_conn.is_closed:
            await _consumer_conn.close()
    except Exception:
        pass

    try:
        await publisher.close()
    except Exception:
        pass


app = FastAPI(title="Booking Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "booking-service",
        "events_enabled": publisher.enabled,
        "exchange_name": EXCHANGE_NAME,
        "rabbit_url_set": bool(RABBIT_URL),
        "outbox": await outbox_stats(),
    }


@app.get("/debug/rabbit")
async def debug_rabbit():
    return {
        "service": "booking-service",
        "rabbit_url_set": bool(RABBIT_URL),
        "exchange_name": EXCHANGE_NAME,
        "consumer": {
            "queue_name": QUEUE_NAME,
            "routing_keys": ROUTING_KEYS,
        },
    }