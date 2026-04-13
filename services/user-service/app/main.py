from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .api.routes import router
from .infrastructure.config import SERVICE_LOG_PREFIX, SERVICE_NAME
from .infrastructure.messaging import publisher, RABBIT_URL, EXCHANGE_NAME
from .infrastructure.outbox_worker import worker, outbox_stats

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"{SERVICE_LOG_PREFIX} starting up...")
    try:
        await publisher.start()
    except Exception as e:
        print(f"{SERVICE_LOG_PREFIX} publisher start failed (ok): {type(e).__name__}: {e}")

    await worker.start()

    yield

    print(f"{SERVICE_LOG_PREFIX} shutting down...")
    try:
        await worker.stop()
    except Exception:
        pass
    try:
        await publisher.close()
    except Exception:
        pass

app = FastAPI(title="User Service", lifespan=lifespan)
app.include_router(router)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "events_enabled": publisher.enabled,
        "exchange_name": EXCHANGE_NAME,
        "rabbit_url_set": bool(RABBIT_URL),
        "outbox": await outbox_stats(),
    }

@app.get("/debug/rabbit")
async def debug_rabbit():
    return {
        "service": SERVICE_NAME,
        "rabbit_url_set": bool(RABBIT_URL),
        "exchange_name": EXCHANGE_NAME,
        "publisher": {"enabled": publisher.enabled},
    }