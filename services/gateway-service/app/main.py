from fastapi import FastAPI, Depends
from typing import List

from .schemas import *
from .clients import *
from .security import get_current_user
from .rbac import require_role
from .middleware import RequestLoggingMiddleware, RateLimitMiddleware

app = FastAPI(title="Smart API Gateway")

# Middleware order: logging wraps everything; rate limit applies early
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_per_minute=120)


@app.get("/health")
async def health():
    return {"status": "gateway running"}


# ================= AUTH (PUBLIC) =================

@app.post("/register")
async def register(data: Register):
    return await register_user(data.model_dump())


@app.post("/login", response_model=TokenResponse)
async def login(data: Login):
    return await login_user(data.model_dump())


# ================= USER (PROTECTED) =================

@app.post("/users")
async def create_user_endpoint(
    data: CreateUser,
    user=Depends(get_current_user),
):
    require_role(user, ["user", "admin"])
    return await create_user(data.model_dump())


@app.put("/users/{email}/location")
async def update_user_location_endpoint(
    email: str,
    data: UpdateUserLocation,
    user=Depends(get_current_user),
):
    require_role(user, ["user", "admin"])
    return await update_user_location(email, data.model_dump())


@app.get("/users/{email}")
async def get_user_endpoint(
    email: str,
    user=Depends(get_current_user),
):
    require_role(user, ["user", "admin"])
    return await get_user(email)


# ================= HANDYMAN (PROTECTED) =================

@app.post("/handymen")
async def create_handyman_endpoint(
    data: CreateHandyman,
    user=Depends(get_current_user),
):
    require_role(user, ["handyman", "admin"])
    return await create_handyman(data.model_dump())


@app.put("/handymen/{email}/location")
async def update_handyman_location_endpoint(
    email: str,
    data: UpdateHandymanLocation,
    user=Depends(get_current_user),
):
    require_role(user, ["handyman", "admin"])
    return await update_handyman_location(email, data.model_dump())


@app.get("/handymen/{email}")
async def get_handyman_endpoint(
    email: str,
    user=Depends(get_current_user),
):
    require_role(user, ["handyman", "admin"])
    return await get_handyman(email)


@app.get("/handymen")
async def list_handymen_endpoint(
    user=Depends(get_current_user),
):
    require_role(user, ["user", "admin"])
    return await list_handymen()


# ================= AVAILABILITY (PROTECTED) =================

@app.post("/availability/{email}")
async def set_availability_endpoint(
    email: str,
    data: SetAvailability,
    user=Depends(get_current_user),
):
    require_role(user, ["handyman", "admin"])
    return await set_availability(email, data.model_dump())


@app.get("/availability/{email}")
async def get_availability_endpoint(
    email: str,
    user=Depends(get_current_user),
):
    require_role(user, ["user", "handyman", "admin"])
    return await get_availability(email)


@app.delete("/availability/{email}")
async def clear_availability_endpoint(
    email: str,
    user=Depends(get_current_user),
):
    require_role(user, ["handyman", "admin"])
    return await clear_availability(email)


# ================= MATCH (PROTECTED) =================

@app.post("/match", response_model=List[MatchResult])
async def match_endpoint(
    data: MatchRequest,
    user=Depends(get_current_user),
):
    require_role(user, ["user", "admin"])
    return await match_request(data.model_dump())
