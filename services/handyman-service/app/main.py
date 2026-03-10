from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routes import router
from .outbox_worker import run_outbox_forever, outbox_stats
from .messaging import publisher, RABBIT_URL, EXCHANGE_NAME
from .skills_catalog import seed_default_catalog_if_empty

_stop = asyncio.Event()
_outbox_task: asyncio.Task | None = None
_last_catalog_seed_status: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _outbox_task, _last_catalog_seed_status

    print("[handyman-service] starting up...")

    _last_catalog_seed_status = await seed_default_catalog_if_empty()
    print(f"[handyman-service] skills catalog seed status: {_last_catalog_seed_status}")

    try:
        await publisher.start()
    except Exception as e:
        print(f"[handyman-service] publisher start failed (ok): {type(e).__name__}: {e}")

    _outbox_task = asyncio.create_task(run_outbox_forever(_stop))

    yield

    print("[handyman-service] shutting down...")
    _stop.set()

    if _outbox_task:
        _outbox_task.cancel()

    try:
        await publisher.close()
    except Exception:
        pass


app = FastAPI(title="Handyman Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "handyman-service",
        "events_enabled": publisher.enabled,
        "exchange_name": EXCHANGE_NAME,
        "rabbit_url_set": bool(RABBIT_URL),
        "outbox": await outbox_stats(),
        "skills_catalog_seed": _last_catalog_seed_status,
    }


@app.get("/debug/rabbit")
async def debug_rabbit():
    return {
        "service": "handyman-service",
        "rabbit_url_set": bool(RABBIT_URL),
        "exchange_name": EXCHANGE_NAME,
        "publisher": {"enabled": publisher.enabled},
    }