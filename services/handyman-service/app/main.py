from fastapi import FastAPI
from .routes import router

app = FastAPI(title="Handyman Service")

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "handyman-service"}
