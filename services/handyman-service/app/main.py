from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routes import router
from .outbox_worker import run_outbox_forever
from .messaging import publisher


_stop = asyncio.Event()
_outbox_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _outbox_task

    print("[handyman-service] starting up...")
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
    return {"status": "ok", "service": "handyman-service"}