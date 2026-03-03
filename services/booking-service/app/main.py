import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routes import router
from .event_consumer import start_consumer
from .outbox_worker import run_outbox_forever
from .messaging import mq


_stop = asyncio.Event()
_consumer_conn = None
_outbox_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_conn, _outbox_task

    print("[booking-service] starting up...")

    await mq.connect()

    _outbox_task = asyncio.create_task(run_outbox_forever(_stop))
    asyncio.create_task(_consumer_with_retry())

    yield

    print("[booking-service] shutting down...")
    _stop.set()

    if _outbox_task:
        _outbox_task.cancel()

    try:
        if _consumer_conn and not _consumer_conn.is_closed:
            await _consumer_conn.close()
    except Exception:
        pass

    await mq.close()


async def _consumer_with_retry():
    global _consumer_conn
    while not _stop.is_set():
        try:
            _consumer_conn = await start_consumer()
            return
        except Exception as e:
            print(f"[booking-service] consumer connect failed, retrying in 5s: {e}")
            try:
                await asyncio.wait_for(_stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                continue


app = FastAPI(
    title="Booking Service",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "booking-service"}