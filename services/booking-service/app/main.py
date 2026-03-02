import asyncio
from fastapi import FastAPI

from .routes import router
from .publisher import publisher
from .outbox import dispatcher
from .event_consumer import start_consumer

app = FastAPI(title="Booking Service")
app.include_router(router)

_consumer_conn = None
_stop = asyncio.Event()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "booking-service"}


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


@app.on_event("startup")
async def startup():
    try:
        await publisher.start()
    except Exception as e:
        print(f"[booking-service] publisher start failed (will retry via outbox loop anyway): {e}")

    await dispatcher.start()
    asyncio.create_task(_consumer_with_retry())


@app.on_event("shutdown")
async def shutdown():
    global _consumer_conn
    _stop.set()

    try:
        await dispatcher.stop()
    except Exception:
        pass

    try:
        await publisher.close()
    except Exception:
        pass

    try:
        if _consumer_conn and not _consumer_conn.is_closed:
            await _consumer_conn.close()
    except Exception:
        pass