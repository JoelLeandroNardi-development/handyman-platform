import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routes import router
from .messaging import publisher, RABBIT_URL, EXCHANGE_NAME
from .event_consumer import start_consumer, QUEUE_NAME, ROUTING_KEYS
from .expiry_worker import expiry_loop
from .outbox_worker import worker, outbox_stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    consumer_conn = None
    expiry_task = None
    consumer_task = None

    async def consumer_with_retry():
        nonlocal consumer_conn
        if not RABBIT_URL:
            print("[availability-service] RABBIT_URL not set, consumer disabled")
            return

        while not stop_event.is_set():
            try:
                consumer_conn = await start_consumer()
                return
            except Exception as e:
                print(f"[availability-service] consumer connect failed, retrying in 5s: {e}")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=5)
                except asyncio.TimeoutError:
                    continue

    print("[availability-service] starting up...")
    try:
        await publisher.start()
    except Exception as e:
        print(f"[availability-service] publisher start failed (ok): {e}")

    await worker.start()

    expiry_task = asyncio.create_task(expiry_loop(stop_event))
    consumer_task = asyncio.create_task(consumer_with_retry())

    yield

    print("[availability-service] shutting down...")
    stop_event.set()

    try:
        await worker.stop()
    except Exception:
        pass

    if expiry_task:
        try:
            await expiry_task
        except Exception:
            pass

    if consumer_task:
        try:
            await consumer_task
        except Exception:
            pass

    try:
        if consumer_conn and not consumer_conn.is_closed:
            await consumer_conn.close()
    except Exception:
        pass

    try:
        await publisher.close()
    except Exception:
        pass


app = FastAPI(title="Availability Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "availability-service",
        "events_enabled": publisher.enabled,
        "exchange_name": EXCHANGE_NAME,
        "rabbit_url_set": bool(RABBIT_URL),
        "outbox": await outbox_stats(),
    }


@app.get("/debug/rabbit")
async def debug_rabbit():
    return {
        "service": "availability-service",
        "rabbit_url_set": bool(RABBIT_URL),
        "exchange_name": EXCHANGE_NAME,
        "consumer": {
            "queue_name": QUEUE_NAME,
            "routing_keys": ROUTING_KEYS,
        },
    }