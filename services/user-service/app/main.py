from fastapi import FastAPI

from .routes import router
from .rabbitmq import publisher
from .outbox import dispatcher

app = FastAPI(title="User Service")
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "user-service"}


@app.on_event("startup")
async def startup():
    try:
        await publisher.start()
    except Exception as e:
        print(f"[user-service] publisher start failed: {e}")

    await dispatcher.start()


@app.on_event("shutdown")
async def shutdown():
    try:
        await dispatcher.stop()
    except Exception:
        pass
    try:
        await publisher.close()
    except Exception:
        pass