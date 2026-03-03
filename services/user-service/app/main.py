from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routes import router
from .messaging import publisher
from .outbox_worker import worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[user-service] starting up...")
    try:
        await publisher.start()
    except Exception as e:
        # should not happen with best-effort shared publisher, but keep safe
        print(f"[user-service] publisher start failed (ok): {type(e).__name__}: {e}")

    await worker.start()

    yield

    print("[user-service] shutting down...")
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
    return {"status": "ok", "service": "user-service"}