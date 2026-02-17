from fastapi import FastAPI
from shared.redis import redis_client

app = FastAPI()

TTL = 15

@app.post("/heartbeat/{handyman_id}")
async def heartbeat(handyman_id: int):
    await redis_client.set(f"availability:{handyman_id}", "1", ex=TTL)
    return {"status": "online"}

@app.get("/status/{handyman_id}")
async def status(handyman_id: int):
    online = await redis_client.exists(f"availability:{handyman_id}")
    return {"online": bool(online)}
