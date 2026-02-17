import os
import httpx
import redis
from fastapi import FastAPI, Request, HTTPException

REDIS_URL = os.getenv("REDIS_URL")

r = redis.Redis.from_url(REDIS_URL)

AUTH_SERVICE = "http://auth-service:8000"
USER_SERVICE = "http://user-service:8000"

app = FastAPI()

RATE_LIMIT = 100

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    ip = request.client.host
    key = f"rate:{ip}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 60)
    if count > RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests")
    return await call_next(request)

@app.api_route("/auth/{path:path}", methods=["GET", "POST"])
async def proxy_auth(path: str, request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.request(request.method, f"{AUTH_SERVICE}/{path}", json=await request.json())
        return resp.json()

@app.api_route("/users/{path:path}", methods=["GET", "POST"])
async def proxy_users(path: str, request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.request(request.method, f"{USER_SERVICE}/{path}", json=await request.json())
        return resp.json()
