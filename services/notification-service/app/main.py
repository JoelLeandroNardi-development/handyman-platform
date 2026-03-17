from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .consumer import consume_forever
from .db import Base, engine
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    consumer_task = asyncio.create_task(consume_forever(stop_event))
    print(json.dumps({"service": "notification-service", "event": "startup_complete"}))

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


app = FastAPI(title="notification-service", version="0.1.0", lifespan=lifespan)
app.include_router(router)
