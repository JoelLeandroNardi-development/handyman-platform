import asyncio
from fastapi import FastAPI

from .routes import router
from .event_consumer import start_consumer

app = FastAPI(title="Match Service")

app.include_router(router)

_consumer_connection = None


@app.get("/health")
async def health():
    return {"status": "ok", "service": "match-service"}


@app.on_event("startup")
async def startup():
    global _consumer_connection
    _consumer_connection = await start_consumer()


@app.on_event("shutdown")
async def shutdown():
    global _consumer_connection
    if _consumer_connection and not _consumer_connection.is_closed:
        await _consumer_connection.close()
