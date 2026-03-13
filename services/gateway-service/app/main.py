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


def _user_email(payload: dict) -> str:
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return str(email)


def _has_role(payload: dict, role: str) -> bool:
    roles = payload.get("roles") or []
    return role.lower() in {str(r).lower() for r in roles}


def _auth_user_has_any_role(auth_user: dict, allowed_roles: list[str]) -> bool:
    roles = {str(r).lower() for r in (auth_user.get("roles") or [])}
    allowed = {str(r).lower() for r in allowed_roles}
    return not roles.isdisjoint(allowed)


async def _get_auth_user_after_register(email: str, request_id: str) -> dict:
    try:
        return await get_auth_user_by_email(email, request_id=request_id, user_payload=None)
    except HTTPException as e:
        raise HTTPException(
            status_code=502,
            detail=f"Auth user was registered but could not be fetched afterwards. status={e.status_code}"
        )


async def _booking_owned_or_admin(booking_id: str, payload: dict, request_id: str) -> dict:
    booking = await get_booking(booking_id, request_id=request_id, user_payload=payload)

    if _has_role(payload, "admin"):
        return booking

    current_email = _user_email(payload)
    is_user_owner = booking.get("user_email") == current_email
    is_handyman_owner = booking.get("handyman_email") == current_email

    if is_user_owner or is_handyman_owner:
        return booking

    raise HTTPException(status_code=403, detail="Forbidden for this booking")


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


@app.post("/register", tags=["Auth"])
async def register(data: Register, request: Request):
    return await register_user(data.model_dump(), request_id=request.state.request_id)


@app.post("/login", response_model=TokenResponse, tags=["Auth"])
async def login(data: Login, request: Request):
    return await login_user(data.model_dump(), request_id=request.state.request_id)


@app.get("/auth-users", response_model=List[AuthUserResponse], tags=["Auth"])
async def admin_list_auth_users(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    require_role(user, ["admin"])
    return await list_auth_users(
        request_id=request.state.request_id,
        user_payload=user,
        limit=limit,
        offset=offset,
    )


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


@app.post("/onboarding/user", response_model=OnboardingUserResponse, tags=["Auth"])
async def onboarding_user(data: OnboardingUserRequest, request: Request):
    await register_user(
        {
            "email": data.email,
            "password": data.password,
            "roles": list(dict.fromkeys([*(data.roles or []), "user"])),
        },
        request_id=request.state.request_id,
    )

    auth_user = await _get_auth_user_after_register(data.email, request.state.request_id)

    if not _auth_user_has_any_role(auth_user, ["user", "admin"]):
        raise HTTPException(status_code=422, detail="Auth user must have role user or admin")

    user_profile = await create_user(
        {
            "email": data.email,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "phone": data.phone,
            "national_id": data.national_id,
            "address_line": data.address_line,
            "postal_code": data.postal_code,
            "city": data.city,
            "country": data.country,
            "latitude": data.latitude,
            "longitude": data.longitude,
        },
        request_id=request.state.request_id,
        user_payload=None,
    )

    return {
        "auth_user": auth_user,
        "user_profile": user_profile,
    }


@app.post("/onboarding/handyman", response_model=OnboardingHandymanResponse, tags=["Auth"])
async def onboarding_handyman(data: OnboardingHandymanRequest, request: Request):
    await register_user(
        {
            "email": data.email,
            "password": data.password,
            "roles": list(dict.fromkeys([*(data.roles or []), "handyman"])),
        },
        request_id=request.state.request_id,
    )

    auth_user = await _get_auth_user_after_register(data.email, request.state.request_id)

    if not _auth_user_has_any_role(auth_user, ["handyman", "admin"]):
        raise HTTPException(status_code=422, detail="Auth user must have role handyman or admin")

    handyman_profile = await create_handyman(
        {
            "email": data.email,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "phone": data.phone,
            "national_id": data.national_id,
            "address_line": data.address_line,
            "postal_code": data.postal_code,
            "city": data.city,
            "country": data.country,
            "skills": data.skills,
            "years_experience": data.years_experience,
            "service_radius_km": data.service_radius_km,
            "latitude": data.latitude,
            "longitude": data.longitude,
        },
        request_id=request.state.request_id,
        user_payload=None,
    )

    return {
        "auth_user": auth_user,
        "handyman_profile": handyman_profile,
    }


@app.post("/onboarding/combined", response_model=OnboardingCombinedResponse, tags=["Auth"])
async def onboarding_combined(data: OnboardingCombinedRequest, request: Request):
    await register_user(
        {
            "email": data.email,
            "password": data.password,
            "roles": list(dict.fromkeys([*(data.roles or []), "user", "handyman"])),
        },
        request_id=request.state.request_id,
    )

    auth_user = await _get_auth_user_after_register(data.email, request.state.request_id)

    if not _auth_user_has_any_role(auth_user, ["user", "admin"]):
        raise HTTPException(status_code=422, detail="Auth user must have role user or admin")

    if not _auth_user_has_any_role(auth_user, ["handyman", "admin"]):
        raise HTTPException(status_code=422, detail="Auth user must have role handyman or admin")

    user_profile = await create_user(
        {
            "email": data.email,
            "first_name": data.user_profile.first_name,
            "last_name": data.user_profile.last_name,
            "phone": data.user_profile.phone,
            "national_id": data.user_profile.national_id,
            "address_line": data.user_profile.address_line,
            "postal_code": data.user_profile.postal_code,
            "city": data.user_profile.city,
            "country": data.user_profile.country,
            "latitude": data.user_profile.latitude,
            "longitude": data.user_profile.longitude,
        },
        request_id=request.state.request_id,
        user_payload=None,
    )

    handyman_profile = await create_handyman(
        {
            "email": data.email,
            "first_name": data.handyman_profile.first_name,
            "last_name": data.handyman_profile.last_name,
            "phone": data.handyman_profile.phone,
            "national_id": data.handyman_profile.national_id,
            "address_line": data.handyman_profile.address_line,
            "postal_code": data.handyman_profile.postal_code,
            "city": data.handyman_profile.city,
            "country": data.handyman_profile.country,
            "skills": data.handyman_profile.skills,
            "years_experience": data.handyman_profile.years_experience,
            "service_radius_km": data.handyman_profile.service_radius_km,
            "latitude": data.handyman_profile.latitude,
            "longitude": data.handyman_profile.longitude,
        },
        request_id=request.state.request_id,
        user_payload=None,
    )

    return {
        "auth_user": auth_user,
        "user_profile": user_profile,
        "handyman_profile": handyman_profile,
    }


@app.get("/me", response_model=MeResponse, tags=["Auth"])
async def get_me(request: Request, user=Depends(get_current_user)):
    email = _user_email(user)
    roles = list(user.get("roles") or [])

    user_profile = None
    handyman_profile = None

    if _has_role(user, "user") or _has_role(user, "admin"):
        try:
            user_profile = await get_user(email, request_id=request.state.request_id, user_payload=user)
        except HTTPException as e:
            if e.status_code != 404:
                raise

    if _has_role(user, "handyman") or _has_role(user, "admin"):
        try:
            handyman_profile = await get_handyman(email, request_id=request.state.request_id, user_payload=user)
        except HTTPException as e:
            if e.status_code != 404:
                raise

    return MeResponse(
        email=email,
        roles=roles,
        user_profile=user_profile,
        handyman_profile=handyman_profile,
    )


@app.post("/users", tags=["Users"])
async def create_user_endpoint(data: CreateUser, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])

    try:
        auth_user = await get_auth_user_by_email(data.email, request_id=request.state.request_id, user_payload=user)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=422, detail="Auth user must exist before creating user profile")
        raise

    if not _auth_user_has_any_role(auth_user, ["user", "admin"]):
        raise HTTPException(status_code=422, detail="Auth user must have role user or admin")

    return await create_user(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.put("/users/{email}/location", tags=["Users"])
async def update_user_location_endpoint(email: str, data: UpdateUserLocation, request: Request, user=Depends(get_current_user)):
    if not _has_role(user, "admin") and _user_email(user) != email:
        raise HTTPException(status_code=403, detail="Cannot update another user's location")
    require_role(user, ["user", "admin"])
    return await update_user_location(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/users/{email}", tags=["Users"])
async def get_user_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_user(email, request_id=request.state.request_id, user_payload=user)


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


@app.get("/me/user", response_model=UserResponse, tags=["Users"])
async def get_me_user(request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await get_user(_user_email(user), request_id=request.state.request_id, user_payload=user)


@app.put("/me", response_model=UserResponse, tags=["Users"])
async def update_me(data: UpdateUser, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await update_user(_user_email(user), data.model_dump(), request_id=request.state.request_id, user_payload=user)


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

    try:
        auth_user = await get_auth_user_by_email(data.email, request_id=request.state.request_id, user_payload=user)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=422, detail="Auth user must exist before creating handyman profile")
        raise

    if not _auth_user_has_any_role(auth_user, ["handyman", "admin"]):
        raise HTTPException(status_code=422, detail="Auth user must have role handyman or admin")

    return await create_handyman(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/handymen/{email}", tags=["Handymen"])
async def get_handyman_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_handyman(email, request_id=request.state.request_id, user_payload=user)


@app.put("/handymen/{email}/location", tags=["Handymen"])
async def update_handyman_location_endpoint(email: str, data: UpdateHandymanLocation, request: Request, user=Depends(get_current_user)):
    if not _has_role(user, "admin") and _user_email(user) != email:
        raise HTTPException(status_code=403, detail="Cannot update another handyman's location")
    require_role(user, ["handyman", "admin"])
    return await update_handyman_location_and_fetch(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.put("/handymen/{email}", response_model=HandymanResponse, tags=["Handymen"])
async def admin_update_handyman_endpoint(email: str, data: UpdateHandyman, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await update_handyman(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.delete("/handymen/{email}", tags=["Handymen"])
async def admin_delete_handyman_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await delete_handyman(email, request_id=request.state.request_id, user_payload=user)


@app.get("/me/handyman", response_model=HandymanResponse, tags=["Handymen"])
async def get_me_handyman(request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await get_handyman(_user_email(user), request_id=request.state.request_id, user_payload=user)


@app.put("/me/handyman", response_model=HandymanResponse, tags=["Handymen"])
async def update_me_handyman(data: UpdateHandyman, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await update_handyman(_user_email(user), data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/skills-catalog", tags=["Handymen"])
async def get_skills_catalog_endpoint(
    request: Request,
    user=Depends(get_current_user),
    active_only: bool = Query(True),
):
    require_role(user, ["user", "handyman", "admin"])
    return await get_skills_catalog(
        request_id=request.state.request_id,
        user_payload=user,
        active_only=active_only,
    )


@app.get("/skills-catalog/flat", response_model=SkillCatalogFlatResponse, tags=["Handymen"])
async def get_skills_catalog_flat_endpoint(
    request: Request,
    user=Depends(get_current_user),
    active_only: bool = Query(True),
):
    require_role(user, ["user", "handyman", "admin"])
    return await get_skills_catalog_flat(
        request_id=request.state.request_id,
        user_payload=user,
        active_only=active_only,
    )


@app.put("/admin/skills-catalog", tags=["Handymen"])
async def replace_skills_catalog_endpoint(
    data: SkillCatalogReplaceRequest,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await replace_skills_catalog(
        data.model_dump(),
        request_id=request.state.request_id,
        user_payload=user,
    )


@app.patch("/admin/skills-catalog", tags=["Handymen"])
async def patch_skills_catalog_endpoint(
    data: SkillCatalogPatchRequest,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await patch_skills_catalog(
        data.model_dump(),
        request_id=request.state.request_id,
        user_payload=user,
    )


@app.get("/admin/handymen/invalid-skills", response_model=InvalidHandymanSkillsResponse, tags=["Handymen"])
async def invalid_handymen_skills_endpoint(
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await get_handymen_with_invalid_skills(
        request_id=request.state.request_id,
        user_payload=user,
    )


@app.post("/availability/{email}", tags=["Availability"])
async def set_availability_endpoint(email: str, data: SetAvailability, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await set_availability(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/availability/{email}", tags=["Availability"])
async def get_availability_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_availability(email, request_id=request.state.request_id, user_payload=user)


@app.delete("/availability/{email}", tags=["Availability"])
async def clear_availability_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await clear_availability(email, request_id=request.state.request_id, user_payload=user)


@app.get("/availability", tags=["Availability"])
async def admin_list_all_availability(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(200, ge=1, le=1000),
    cursor: int = Query(0, ge=0),
):
    require_role(user, ["admin"])
    return await list_all_availability(request_id=request.state.request_id, user_payload=user, limit=limit, cursor=cursor)


@app.get("/me/availability", tags=["Availability"])
async def get_my_availability(request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await get_availability(_user_email(user), request_id=request.state.request_id, user_payload=user)


@app.post("/me/availability", tags=["Availability"])
async def set_my_availability(data: SetAvailability, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await set_availability(_user_email(user), data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.delete("/me/availability", tags=["Availability"])
async def clear_my_availability(request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await clear_availability(_user_email(user), request_id=request.state.request_id, user_payload=user)


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


@app.post("/bookings", response_model=BookingResponse, tags=["Bookings"])
async def create_booking_endpoint(data: CreateBookingRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])

    if not _has_role(user, "admin") and data.user_email != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot create booking for another user")

    return await create_booking(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.get("/bookings/{booking_id}", response_model=BookingResponse, tags=["Bookings"])
async def get_booking_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "handyman", "admin"])
    booking = await _booking_owned_or_admin(booking_id, user, request.state.request_id)
    return booking


@app.post("/bookings/{booking_id}/confirm", response_model=ConfirmBookingResponse, tags=["Bookings"])
async def confirm_booking_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin") and booking.get("handyman_email") != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot confirm another handyman's booking")

    return await confirm_booking(booking_id, request_id=request.state.request_id, user_payload=user)


@app.post("/bookings/{booking_id}/cancel", response_model=CancelBookingResponse, tags=["Bookings"])
async def cancel_booking_endpoint(booking_id: str, data: CancelBookingRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin"):
        current_email = _user_email(user)
        is_user_owner = booking.get("user_email") == current_email
        if not (is_user_owner):
            raise HTTPException(status_code=403, detail="Cannot cancel another user's booking")

    return await cancel_booking(booking_id, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@app.post("/bookings/{booking_id}/complete/user", response_model=CompleteBookingResponse, tags=["Bookings"])
async def complete_booking_user_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin") and booking.get("user_email") != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot complete another user's booking as user")

    return await complete_booking_as_user(booking_id, request_id=request.state.request_id, user_payload=user)


@app.post("/bookings/{booking_id}/complete/handyman", response_model=CompleteBookingResponse, tags=["Bookings"])
async def complete_booking_handyman_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin") and booking.get("handyman_email") != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot complete another handyman's booking as handyman")

    return await complete_booking_as_handyman(booking_id, request_id=request.state.request_id, user_payload=user)


@app.post("/bookings/{booking_id}/reject", response_model=RejectBookingResponse, tags=["Bookings"])
async def reject_booking_completion_endpoint(
    booking_id: str,
    data: RejectBookingRequest,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["handyman", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin") and booking.get("handyman_email") != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot reject another handyman's booking")

    return await reject_booking(
        booking_id,
        data.model_dump(),
        request_id=request.state.request_id,
        user_payload=user,
    )


@app.get("/me/bookings", response_model=List[BookingResponse], tags=["Bookings"])
async def get_my_bookings(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(default=None),
):
    require_role(user, ["user", "admin"])
    return await list_bookings(
        request_id=request.state.request_id,
        user_payload=user,
        limit=limit,
        offset=offset,
        status=status,
        user_email=_user_email(user),
        handyman_email=None,
    )


@app.get("/me/jobs", response_model=List[BookingResponse], tags=["Bookings"])
async def get_my_jobs(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(default=None),
):
    require_role(user, ["handyman", "admin"])
    return await list_bookings(
        request_id=request.state.request_id,
        user_payload=user,
        limit=limit,
        offset=offset,
        status=status,
        user_email=None,
        handyman_email=_user_email(user),
    )


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