import asyncio
from fastapi import FastAPI

from .routes import router
from .event_consumer import start_consumer_with_retry

app = FastAPI(title="Match Service")

app.include_router(router)

_consumer_connection = None
_stop_event = asyncio.Event()
_consumer_task: asyncio.Task | None = None


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "match-service",
        "events_enabled": _consumer_connection is not None,
    }


@app.on_event("startup")
async def startup():
    global _consumer_task, _consumer_connection

    async def runner():
        global _consumer_connection
        _consumer_connection = await start_consumer_with_retry(_stop_event)

    _consumer_task = asyncio.create_task(runner())


@app.on_event("shutdown")
async def shutdown():
    global _consumer_connection, _consumer_task
    _stop_event.set()

    try:
        if _consumer_task:
            await _consumer_task
    except Exception:
        pass

    try:
        if _consumer_connection and not _consumer_connection.is_closed:
            await _consumer_connection.close()
    except Exception:
        pass

    _consumer_connection = None
