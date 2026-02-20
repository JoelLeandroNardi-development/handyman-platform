from fastapi import FastAPI
from .routes import router
from .rabbitmq import publisher

app = FastAPI(title="Availability Service")

app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "availability-service",
        "events_enabled": publisher.enabled,
    }


@app.on_event("startup")
async def startup():
    # Never crash the service if RabbitMQ is down/unreachable at startup.
    try:
        await publisher.connect()
    except Exception as e:
        # Keep serving HTTP even if events are temporarily unavailable.
        print(f"[availability-service] RabbitMQ connect failed at startup; continuing without events: {e}")


@app.on_event("shutdown")
async def shutdown():
    try:
        await publisher.close()
    except Exception:
        pass
