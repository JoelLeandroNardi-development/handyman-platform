from fastapi import APIRouter, Depends, Request, HTTPException, Query
from typing import List

from ..schemas import (
    Register,
    Login,
    TokenResponse,
    AuthUserResponse,
    UpdateAuthUser,
    OnboardingUserRequest,
    OnboardingUserResponse,
    OnboardingHandymanRequest,
    OnboardingHandymanResponse,
    OnboardingCombinedRequest,
    OnboardingCombinedResponse,
    MeResponse,
)
from ..clients import (
    register_user,
    login_user,
    list_auth_users,
    get_auth_user,
    get_auth_user_by_email,
    update_auth_user,
    delete_auth_user,
    create_user,
    create_handyman,
    get_user,
    get_handyman,
)
from ..security import get_current_user
from ..rbac import require_role
from ..helpers import (
    _user_email,
    _has_role,
    _auth_user_has_any_role,
    _get_auth_user_after_register,
)

router = APIRouter()


@router.post("/register", tags=["Auth"])
async def register(data: Register, request: Request):
    return await register_user(data.model_dump(), request_id=request.state.request_id)


@router.post("/login", response_model=TokenResponse, tags=["Auth"])
async def login(data: Login, request: Request):
    return await login_user(data.model_dump(), request_id=request.state.request_id)


@router.get("/auth-users", response_model=List[AuthUserResponse], tags=["Auth"])
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


@router.get("/auth-users/{user_id}", response_model=AuthUserResponse, tags=["Auth"])
async def admin_get_auth_user(user_id: int, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_auth_user(user_id, request_id=request.state.request_id, user_payload=user)


@router.get("/auth-users/by-email/{email}", response_model=AuthUserResponse, tags=["Auth"])
async def admin_get_auth_user_by_email(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_auth_user_by_email(email, request_id=request.state.request_id, user_payload=user)


@router.put("/auth-users/{user_id}", response_model=AuthUserResponse, tags=["Auth"])
async def admin_update_auth_user(user_id: int, data: UpdateAuthUser, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await update_auth_user(user_id, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.delete("/auth-users/{user_id}", tags=["Auth"])
async def admin_delete_auth_user(user_id: int, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await delete_auth_user(user_id, request_id=request.state.request_id, user_payload=user)


@router.post("/onboarding/user", response_model=OnboardingUserResponse, tags=["Auth"])
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


@router.post("/onboarding/handyman", response_model=OnboardingHandymanResponse, tags=["Auth"])
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


@router.post("/onboarding/combined", response_model=OnboardingCombinedResponse, tags=["Auth"])
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


@router.get("/me", response_model=MeResponse, tags=["Auth"])
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
