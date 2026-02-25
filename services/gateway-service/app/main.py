import time
import asyncio
import httpx
from fastapi import FastAPI, Depends, Request, HTTPException
from typing import List

from .schemas import *
from .clients import *
from .security import get_current_user
from .rbac import require_role
from .middleware import RequestLoggingMiddleware, RateLimitMiddleware
from .config import (
    AUTH_SERVICE_URL,
    USER_SERVICE_URL,
    HANDYMAN_SERVICE_URL,
    AVAILABILITY_SERVICE_URL,
    MATCH_SERVICE_URL,
)

OPENAPI_TAGS = [
    {"name": "System", "description": "Gateway operational endpoints (health, breakers, admin ops)."},
    {"name": "Auth", "description": "Authentication endpoints proxied to auth-service."},
    {"name": "Users", "description": "User profile endpoints proxied to user-service."},
    {"name": "Handymen", "description": "Handyman endpoints proxied to handyman-service."},
    {"name": "Availability", "description": "Availability endpoints proxied to availability-service."},
    {"name": "Match", "description": "Match endpoints proxied to match-service."},
]

app = FastAPI(title="Smart API Gateway", openapi_tags=OPENAPI_TAGS)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_per_minute=120)


def _breaker_registry():
    return {
        "auth-service": cb_auth,
        "user-service": cb_user,
        "handyman-service": cb_handyman,
        "availability-service": cb_availability,
        "match-service": cb_match,
    }


# ================= SYSTEM =================

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "gateway-service"}


@app.get("/system/health", tags=["System"])
async def system_health(request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])

    services = {
        "auth-service": f"{AUTH_SERVICE_URL}/health",
        "user-service": f"{USER_SERVICE_URL}/health",
        "handyman-service": f"{HANDYMAN_SERVICE_URL}/health",
        "availability-service": f"{AVAILABILITY_SERVICE_URL}/health",
        "match-service": f"{MATCH_SERVICE_URL}/health",
    }

    async def check(name: str, url: str):
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(url, headers={"X-Request-Id": request.state.request_id})
                latency_ms = (time.perf_counter() - start) * 1000
                return {
                    "service": name,
                    "status": "up" if r.status_code == 200 else "down",
                    "http_status": r.status_code,
                    "latency_ms": round(latency_ms, 2),
                }
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "service": name,
                "status": "down",
                "error": str(e),
                "latency_ms": round(latency_ms, 2),
            }

    results = await asyncio.gather(*[check(n, u) for n, u in services.items()])
    overall = "up" if all(r.get("status") == "up" for r in results) else "degraded"
    return {"status": overall, "services": results}


@app.get("/system/breakers", tags=["System"])
async def breakers_status(user=Depends(get_current_user)):
    require_role(user, ["admin"])
    registry = _breaker_registry()
    statuses = await asyncio.gather(*[b.status() for b in registry.values()])
    statuses.sort(key=lambda x: x["name"])
    return {"breakers": statuses}


@app.post("/system/breakers/{name}/close", tags=["System"])
async def breaker_close(name: str, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    registry = _breaker_registry()
    b = registry.get(name)
    if not b:
        raise HTTPException(status_code=404, detail="Breaker not found")
    await b.close()
    return {"message": "closed", "breaker": await b.status()}


@app.post("/system/breakers/{name}/open", tags=["System"])
async def breaker_open(name: str, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    registry = _breaker_registry()
    b = registry.get(name)
    if not b:
        raise HTTPException(status_code=404, detail="Breaker not found")
    await b.open()
    return {"message": "opened", "breaker": await b.status()}


# ================= AUTH =================

@app.post("/register", tags=["Auth"])
async def register(data: Register, request: Request):
    return await register_user(data.model_dump(), request_id=request.state.request_id)


@app.post("/login", response_model=TokenResponse, tags=["Auth"])
async def login(data: Login, request: Request):
    return await login_user(data.model_dump(), request_id=request.state.request_id)


# ================= USERS =================

@app.post("/users", tags=["Users"])
async def create_user_endpoint(data: CreateUser, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await create_user(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.put("/users/{email}/location", tags=["Users"])
async def update_user_location_endpoint(email: str, data: UpdateUserLocation, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await update_user_location(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/users/{email}", tags=["Users"])
async def get_user_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await get_user(email, request_id=request.state.request_id, user_payload=user)


# ================= HANDYMEN =================

@app.get("/handymen", tags=["Handymen"])
async def list_handymen_endpoint(request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "handyman", "admin"])
    return await list_handymen(request_id=request.state.request_id, user_payload=user)


@app.post("/handymen", tags=["Handymen"])
async def create_handyman_endpoint(data: CreateHandyman, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await create_handyman(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/handymen/{email}", tags=["Handymen"])
async def get_handyman_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await get_handyman(email, request_id=request.state.request_id, user_payload=user)


@app.put("/handymen/{email}/location", tags=["Handymen"])
async def update_handyman_location_endpoint(email: str, data: UpdateHandymanLocation, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await update_handyman_location_and_fetch(
        email,
        data.model_dump(),
        request_id=request.state.request_id,
        user_payload=user,
    )


# ================= AVAILABILITY =================

@app.post("/availability/{email}", tags=["Availability"])
async def set_availability_endpoint(email: str, data: SetAvailability, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await set_availability(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/availability/{email}", tags=["Availability"])
async def get_availability_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "handyman", "admin"])
    return await get_availability(email, request_id=request.state.request_id, user_payload=user)


@app.delete("/availability/{email}", tags=["Availability"])
async def clear_availability_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await clear_availability(email, request_id=request.state.request_id, user_payload=user)


# ================= MATCH =================

@app.post("/match", response_model=List[MatchResult], tags=["Match"])
async def match_endpoint(data: MatchRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await match_request(data.model_dump(), request_id=request.state.request_id, user_payload=user)