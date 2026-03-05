import time
import asyncio
import httpx
from fastapi import FastAPI, Depends, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

from .schemas import *
from .clients import *
from .security import get_current_user
from .rbac import require_role
from .middleware import RequestLoggingMiddleware, RateLimitMiddleware
from .config import SERVICE_BASE_URLS

origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

OPENAPI_TAGS = [
    {"name": "System"},
    {"name": "Auth"},
    {"name": "Users"},
    {"name": "Handymen"},
    {"name": "Availability"},
    {"name": "Match"},
    {"name": "Bookings"},
]

app = FastAPI(title="Smart API Gateway", openapi_tags=OPENAPI_TAGS)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_per_minute=120)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _breaker_registry():
    return {
        "auth-service": cb_auth,
        "user-service": cb_user,
        "handyman-service": cb_handyman,
        "availability-service": cb_availability,
        "match-service": cb_match,
        "booking-service": cb_booking,
    }


def _service_urls(path: str) -> Dict[str, str]:
    bases = SERVICE_BASE_URLS()
    return {name: f"{base}{path}" for name, base in bases.items()}


async def _fetch_json(
    *,
    client: httpx.AsyncClient,
    name: str,
    url: str,
    request_id: str,
) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        r = await client.get(url, headers={"X-Request-Id": request_id})
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        try:
            data: Any = r.json()
        except Exception:
            data = {"raw": (r.text or "")[:500]}

        return {
            "service": name,
            "url": url,
            "status": "up" if r.status_code == 200 else "down",
            "http_status": r.status_code,
            "latency_ms": latency_ms,
            "data": data,
        }
    except Exception as e:
        return {
            "service": name,
            "url": url,
            "status": "down",
            "error": str(e),
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "data": None,
        }


def _overall_status(results: List[Dict[str, Any]]) -> str:
    return "up" if all(r.get("status") == "up" for r in results) else "degraded"


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "gateway-service"}


@app.get("/system/health", tags=["System"])
async def system_health(request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    services = _service_urls("/health")

    async with httpx.AsyncClient(timeout=2.0) as client:
        results = await asyncio.gather(
            *[
                _fetch_json(client=client, name=n, url=u, request_id=request.state.request_id)
                for n, u in services.items()
            ]
        )

    results.sort(key=lambda x: x["service"])
    return {"status": _overall_status(results), "services": results}


@app.get("/system/rabbit", tags=["System"])
async def system_rabbit(request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    services = _service_urls("/debug/rabbit")

    async with httpx.AsyncClient(timeout=2.0) as client:
        results = await asyncio.gather(
            *[
                _fetch_json(client=client, name=n, url=u, request_id=request.state.request_id)
                for n, u in services.items()
            ]
        )

    results.sort(key=lambda x: x["service"])
    return {"status": _overall_status(results), "services": results}


@app.get("/system/outbox", tags=["System"])
async def system_outbox(request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    services = _service_urls("/health")

    async with httpx.AsyncClient(timeout=2.0) as client:
        results = await asyncio.gather(
            *[
                _fetch_json(client=client, name=n, url=u, request_id=request.state.request_id)
                for n, u in services.items()
            ]
        )

    compact: List[Dict[str, Any]] = []
    for r in results:
        data = r.get("data") or {}
        outbox = None
        exchange_name = None
        events_enabled = None

        if isinstance(data, dict):
            outbox = data.get("outbox")
            exchange_name = data.get("exchange_name")
            events_enabled = data.get("events_enabled")

        compact.append(
            {
                "service": r["service"],
                "status": r.get("status"),
                "http_status": r.get("http_status"),
                "latency_ms": r.get("latency_ms"),
                "exchange_name": exchange_name,
                "events_enabled": events_enabled,
                "outbox": outbox,
            }
        )

    compact.sort(key=lambda x: x["service"])
    overall = "up" if all(x.get("status") == "up" for x in compact) else "degraded"
    return {"status": overall, "services": compact}


@app.get("/system/breakers", tags=["System"])
async def breakers_status(user=Depends(get_current_user)):
    require_role(user, ["admin"])
    statuses = await asyncio.gather(*[b.status() for b in _breaker_registry().values()])
    statuses.sort(key=lambda x: x["name"])
    return {"breakers": statuses}


@app.post("/system/breakers/{name}/close", tags=["System"])
async def breaker_close(name: str, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    b = _breaker_registry().get(name)
    if not b:
        raise HTTPException(status_code=404, detail="Breaker not found")
    await b.close()
    return {"message": "closed", "breaker": await b.status()}


@app.post("/system/breakers/{name}/open", tags=["System"])
async def breaker_open(name: str, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    b = _breaker_registry().get(name)
    if not b:
        raise HTTPException(status_code=404, detail="Breaker not found")
    await b.open()
    return {"message": "opened", "breaker": await b.status()}


# ---- AUTH ----

@app.post("/register", tags=["Auth"])
async def register(data: Register, request: Request):
    return await register_user(data.model_dump(), request_id=request.state.request_id)


@app.post("/login", response_model=TokenResponse, tags=["Auth"])
async def login(data: Login, request: Request):
    return await login_user(data.model_dump(), request_id=request.state.request_id)


# Auth back-office (admin)

@app.get("/auth-users", response_model=List[AuthUserResponse], tags=["Auth"])
async def admin_list_auth_users(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    require_role(user, ["admin"])
    return await list_auth_users(request_id=request.state.request_id, user_payload=user, limit=limit, offset=offset)


@app.get("/auth-users/{user_id}", response_model=AuthUserResponse, tags=["Auth"])
async def admin_get_auth_user(user_id: int, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_auth_user(user_id, request_id=request.state.request_id, user_payload=user)


@app.get("/auth-users/by-email/{email}", response_model=AuthUserResponse, tags=["Auth"])
async def admin_get_auth_user_by_email(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_auth_user_by_email(email, request_id=request.state.request_id, user_payload=user)


@app.put("/auth-users/{user_id}", response_model=AuthUserResponse, tags=["Auth"])
async def admin_update_auth_user(user_id: int, data: UpdateAuthUser, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await update_auth_user(user_id, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.delete("/auth-users/{user_id}", tags=["Auth"])
async def admin_delete_auth_user(user_id: int, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await delete_auth_user(user_id, request_id=request.state.request_id, user_payload=user)


# ---- USERS ----

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


# Users back-office (admin)

@app.get("/users", response_model=List[UserResponse], tags=["Users"])
async def admin_list_users(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    require_role(user, ["admin"])
    return await list_users(request_id=request.state.request_id, user_payload=user, limit=limit, offset=offset)


@app.put("/users/{email}", response_model=UserResponse, tags=["Users"])
async def admin_update_user_endpoint(email: str, data: UpdateUser, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await update_user(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.delete("/users/{email}", tags=["Users"])
async def admin_delete_user_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await delete_user(email, request_id=request.state.request_id, user_payload=user)


# ---- HANDYMEN ----

@app.get("/handymen", tags=["Handymen"])
async def list_handymen_endpoint(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    require_role(user, ["user", "handyman", "admin"])
    return await list_handymen(request_id=request.state.request_id, user_payload=user, limit=limit, offset=offset)


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
    return await update_handyman_location_and_fetch(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


# Handymen back-office (admin)

@app.put("/handymen/{email}", response_model=HandymanResponse, tags=["Handymen"])
async def admin_update_handyman_endpoint(email: str, data: UpdateHandyman, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await update_handyman(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.delete("/handymen/{email}", tags=["Handymen"])
async def admin_delete_handyman_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await delete_handyman(email, request_id=request.state.request_id, user_payload=user)


# ---- AVAILABILITY ----

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


# Availability back-office (admin)

@app.get("/availability", tags=["Availability"])
async def admin_list_all_availability(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(200, ge=1, le=1000),
    cursor: int = Query(0, ge=0),
):
    require_role(user, ["admin"])
    return await list_all_availability(request_id=request.state.request_id, user_payload=user, limit=limit, cursor=cursor)


# ---- MATCH ----

@app.post("/match", response_model=List[MatchResult], tags=["Match"])
async def match_endpoint(data: MatchRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await match_request(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/match-logs", tags=["Match"])
async def admin_list_match_logs(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    skill: str | None = Query(default=None),
):
    require_role(user, ["admin"])
    return await list_match_logs(request_id=request.state.request_id, user_payload=user, limit=limit, offset=offset, skill=skill)


@app.delete("/match-logs/{log_id}", tags=["Match"])
async def admin_delete_match_log(
    log_id: int,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await delete_match_log(log_id, request_id=request.state.request_id, user_payload=user)


# ---- BOOKINGS ----

@app.post("/bookings", response_model=BookingResponse, tags=["Bookings"])
async def create_booking_endpoint(data: CreateBookingRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await create_booking(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/bookings/{booking_id}", response_model=BookingResponse, tags=["Bookings"])
async def get_booking_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "handyman", "admin"])
    return await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)


@app.post("/bookings/{booking_id}/confirm", response_model=ConfirmBookingResponse, tags=["Bookings"])
async def confirm_booking_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await confirm_booking(booking_id, request_id=request.state.request_id, user_payload=user)


@app.post("/bookings/{booking_id}/cancel", response_model=CancelBookingResponse, tags=["Bookings"])
async def cancel_booking_endpoint(booking_id: str, data: CancelBookingRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await cancel_booking(booking_id, data.model_dump(), request_id=request.state.request_id, user_payload=user)


# Bookings back-office (admin)

@app.get("/bookings", tags=["Bookings"])
async def admin_list_bookings(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(default=None),
    user_email: str | None = Query(default=None),
    handyman_email: str | None = Query(default=None),
):
    require_role(user, ["admin"])
    return await list_bookings(
        request_id=request.state.request_id,
        user_payload=user,
        limit=limit,
        offset=offset,
        status=status,
        user_email=user_email,
        handyman_email=handyman_email,
    )


@app.put("/bookings/{booking_id}", tags=["Bookings"])
async def admin_update_booking_endpoint(
    booking_id: str,
    data: UpdateBookingAdmin,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await admin_update_booking(booking_id, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.delete("/bookings/{booking_id}", tags=["Bookings"])
async def admin_delete_booking_endpoint(
    booking_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await admin_delete_booking(booking_id, request_id=request.state.request_id, user_payload=user)