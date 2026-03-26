from fastapi import APIRouter, Depends, Request, Query

from app.clients.availability_client import (
    set_availability,
    get_availability,
    clear_availability,
    list_all_availability,
)
from app.schemas import (
    SetAvailability,
    AvailabilityMessageResponse,
    AvailabilityResponse,
    AvailabilityListResponse,
)
from app.utils.helpers import _user_email
from app.utils.rbac import require_role
from app.utils.security import get_current_user

router = APIRouter()

@router.post("/availability/{email}", response_model=AvailabilityMessageResponse, tags=["Availability"])
async def set_availability_endpoint(email: str, data: SetAvailability, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await set_availability(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)

@router.get("/availability/{email}", response_model=AvailabilityResponse, tags=["Availability"])
async def get_availability_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_availability(email, request_id=request.state.request_id, user_payload=user)

@router.delete("/availability/{email}", response_model=AvailabilityMessageResponse, tags=["Availability"])
async def clear_availability_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await clear_availability(email, request_id=request.state.request_id, user_payload=user)

@router.get("/availability", response_model=AvailabilityListResponse, tags=["Availability"])
async def admin_list_all_availability(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(200, ge=1, le=1000),
    cursor: int = Query(0, ge=0),
):
    require_role(user, ["admin"])
    return await list_all_availability(request_id=request.state.request_id, user_payload=user, limit=limit, cursor=cursor)

@router.get("/me/availability", response_model=AvailabilityResponse, tags=["Availability"])
async def get_my_availability(request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await get_availability(_user_email(user), request_id=request.state.request_id, user_payload=user)

@router.post("/me/availability", response_model=AvailabilityMessageResponse, tags=["Availability"])
async def set_my_availability(data: SetAvailability, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await set_availability(_user_email(user), data.model_dump(), request_id=request.state.request_id, user_payload=user)

@router.delete("/me/availability", response_model=AvailabilityMessageResponse, tags=["Availability"])
async def clear_my_availability(request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await clear_availability(_user_email(user), request_id=request.state.request_id, user_payload=user)