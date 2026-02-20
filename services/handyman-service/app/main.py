from fastapi import FastAPI
from .routes import router
from .rabbitmq import publisher

app = FastAPI(title="Handyman Service")

app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "handyman-service",
        "events_enabled": publisher.enabled,
    }


@app.on_event("startup")
async def startup():
    try:
        await publisher.connect()
    except Exception as e:
        print(f"[handyman-service] RabbitMQ connect failed at startup; continuing without events: {e}")


@app.on_event("shutdown")
async def shutdown():
    try:
        await publisher.close()
    except Exception:
        pass
