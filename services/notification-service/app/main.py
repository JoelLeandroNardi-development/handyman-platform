from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router
from .infrastructure.consumer import consume_forever
from .infrastructure.config import EVENT_STARTUP_COMPLETE, SERVICE_NAME, SERVICE_VERSION
from .infrastructure.db import Base, engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    consumer_task = asyncio.create_task(consume_forever(stop_event))
    print(json.dumps({"service": SERVICE_NAME, "event": EVENT_STARTUP_COMPLETE}))

    try:
        yield
    finally:
        stop_event.set()

        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        await engine.dispose()

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION, lifespan=lifespan)
app.include_router(router)