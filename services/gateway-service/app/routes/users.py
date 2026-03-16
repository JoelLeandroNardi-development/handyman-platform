from fastapi import APIRouter, Depends, Request, HTTPException, Query
from typing import List

from ..schemas import (
    CreateUser,
    UpdateUserLocation,
    UpdateUser,
    UserResponse,
)
from ..clients import (
    create_user,
    update_user_location,
    get_user,
    list_users,
    update_user,
    delete_user,
    get_auth_user_by_email,
)
from ..security import get_current_user
from ..rbac import require_role
from ..helpers import (
    _user_email,
    _has_role,
    _auth_user_has_any_role,
)

router = APIRouter()


@router.post("/users", tags=["Users"])
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


@router.put("/users/{email}/location", tags=["Users"])
async def update_user_location_endpoint(email: str, data: UpdateUserLocation, request: Request, user=Depends(get_current_user)):
    if not _has_role(user, "admin") and _user_email(user) != email:
        raise HTTPException(status_code=403, detail="Cannot update another user's location")
    require_role(user, ["user", "admin"])
    return await update_user_location(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.get("/users/{email}", tags=["Users"])
async def get_user_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_user(email, request_id=request.state.request_id, user_payload=user)


@router.get("/users", response_model=List[UserResponse], tags=["Users"])
async def admin_list_users(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    require_role(user, ["admin"])
    return await list_users(request_id=request.state.request_id, user_payload=user, limit=limit, offset=offset)


@router.put("/users/{email}", response_model=UserResponse, tags=["Users"])
async def admin_update_user_endpoint(email: str, data: UpdateUser, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await update_user(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.delete("/users/{email}", tags=["Users"])
async def admin_delete_user_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await delete_user(email, request_id=request.state.request_id, user_payload=user)


@router.get("/me/user", response_model=UserResponse, tags=["Users"])
async def get_me_user(request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await get_user(_user_email(user), request_id=request.state.request_id, user_payload=user)


@router.put("/me", response_model=UserResponse, tags=["Users"])
async def update_me(data: UpdateUser, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await update_user(_user_email(user), data.model_dump(), request_id=request.state.request_id, user_payload=user)
