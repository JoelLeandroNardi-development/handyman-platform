from fastapi import FastAPI
from .routes import router
from .publisher import publisher
from .consumer import start_consumer

app = FastAPI(title="Booking Service")
app.include_router(router)

_consumer_conn = None

@app.get("/health")
async def health():
    return {"status": "ok", "service": "booking-service"}

@app.on_event("startup")
async def startup():
    global _consumer_conn
    await publisher.start()
    _consumer_conn = await start_consumer()

@app.on_event("shutdown")
async def shutdown():
    global _consumer_conn
    try:
        await publisher.close()
    except Exception:
        pass
    try:
        if _consumer_conn and not _consumer_conn.is_closed:
            await _consumer_conn.close()
    except Exception:
        pass