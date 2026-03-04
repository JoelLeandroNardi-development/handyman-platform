import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routes import router
from .event_consumer import start_consumer_with_retry, QUEUE_NAME, ROUTING_KEYS
from .outbox_worker import worker
from .messaging import RABBIT_URL, EXCHANGE_NAME


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    consumer_task: asyncio.Task | None = None
    consumer_conn = None

    async def run_consumer():
        nonlocal consumer_conn
        consumer_conn = await start_consumer_with_retry(stop_event)

    await worker.start()
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

        try:
            await worker.stop()
        except Exception:
            pass


app = FastAPI(title="Match Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "match-service",
        "events_enabled": bool(RABBIT_URL),
        "exchange_name": EXCHANGE_NAME,
        "rabbit_url_set": bool(RABBIT_URL),
    }


@app.get("/debug/rabbit")
async def debug_rabbit():
    return {
        "service": "match-service",
        "rabbit_url_set": bool(RABBIT_URL),
        "exchange_name": EXCHANGE_NAME,
        "consumer": {
            "queue_name": QUEUE_NAME,
            "routing_keys": ROUTING_KEYS,
        },
    }