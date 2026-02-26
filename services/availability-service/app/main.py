import os
import asyncio
from fastapi import FastAPI

from .routes import router
from .rabbitmq import publisher, RABBIT_URL
from .event_consumer import start_consumer
from .expiry_worker import expiry_loop

app = FastAPI(title="Availability Service")
app.include_router(router)

_consumer_conn = None
_stop_event = asyncio.Event()
_expiry_task = None

@app.get("/health")
async def health():
    return {"status": "ok", "service": "availability-service", "events_enabled": publisher.enabled}

@app.on_event("startup")
async def startup():
    global _consumer_conn, _expiry_task
    try:
        await publisher.connect()
    except Exception as e:
        print(f"[availability-service] RabbitMQ connect failed at startup; continuing: {e}")

    # start booking consumer (don’t crash service)
    try:
        if RABBIT_URL:
            _consumer_conn = await start_consumer(RABBIT_URL)
    except Exception as e:
        _consumer_conn = None
        print(f"[availability-service] booking consumer failed to start: {e}")

    _expiry_task = asyncio.create_task(expiry_loop(_stop_event))

@app.on_event("shutdown")
async def shutdown():
    global _consumer_conn, _expiry_task
    _stop_event.set()
    if _expiry_task:
        try:
            await _expiry_task
        except Exception:
            pass
    try:
        if _consumer_conn and not _consumer_conn.is_closed:
            await _consumer_conn.close()
    except Exception:
        pass
    try:
        await publisher.close()
    except Exception:
        pass