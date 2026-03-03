import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routes import router
from .event_consumer import start_consumer_with_retry
from .outbox_worker import worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    consumer_task: asyncio.Task | None = None
    consumer_conn = None

    async def run_consumer():
        nonlocal consumer_conn
        consumer_conn = await start_consumer_with_retry(stop_event)

    # start worker (no-op in this service, but keeps architecture consistent)
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
    # We don't expose consumer state here since it's async; just say ok.
    return {"status": "ok", "service": "match-service"}