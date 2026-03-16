from fastapi import APIRouter, Depends, Request, HTTPException, Query
from typing import List

from ..schemas import (
    BookingResponse,
    ConfirmBookingResponse,
    CancelBookingResponse,
    CompleteBookingResponse,
    RejectBookingRequest,
    RejectBookingResponse,
    UpdateBookingAdmin,
    CreateBookingRequest,
    CancelBookingRequest,
    HandymanReviewResponse,
    CreateHandymanReviewRequest,
)
from ..clients import (
    create_booking,
    get_booking,
    confirm_booking,
    cancel_booking,
    complete_booking_as_user,
    complete_booking_as_handyman,
    reject_booking,
    create_handyman_review,
    list_bookings,
    admin_update_booking,
    admin_delete_booking,
)
from ..security import get_current_user
from ..rbac import require_role
from ..helpers import (
    _user_email,
    _has_role,
    _booking_owned_or_admin,
)

router = APIRouter()


@router.post("/bookings", response_model=BookingResponse, tags=["Bookings"])
async def create_booking_endpoint(data: CreateBookingRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])

    if not _has_role(user, "admin") and data.user_email != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot create booking for another user")

    return await create_booking(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.get("/bookings/{booking_id}", response_model=BookingResponse, tags=["Bookings"])
async def get_booking_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "handyman", "admin"])
    booking = await _booking_owned_or_admin(booking_id, user, request.state.request_id)
    return booking


@router.post("/bookings/{booking_id}/confirm", response_model=ConfirmBookingResponse, tags=["Bookings"])
async def confirm_booking_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin") and booking.get("handyman_email") != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot confirm another handyman's booking")

    return await confirm_booking(booking_id, request_id=request.state.request_id, user_payload=user)


@router.post("/bookings/{booking_id}/cancel", response_model=CancelBookingResponse, tags=["Bookings"])
async def cancel_booking_endpoint(booking_id: str, data: CancelBookingRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin"):
        current_email = _user_email(user)
        is_user_owner = booking.get("user_email") == current_email
        if not (is_user_owner):
            raise HTTPException(status_code=403, detail="Cannot cancel another user's booking")

    return await cancel_booking(booking_id, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.post("/bookings/{booking_id}/complete/user", response_model=CompleteBookingResponse, tags=["Bookings"])
async def complete_booking_user_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin") and booking.get("user_email") != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot complete another user's booking as user")

    return await complete_booking_as_user(booking_id, request_id=request.state.request_id, user_payload=user)


@router.post("/bookings/{booking_id}/complete/handyman", response_model=CompleteBookingResponse, tags=["Bookings"])
async def complete_booking_handyman_endpoint(booking_id: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if not _has_role(user, "admin") and booking.get("handyman_email") != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot complete another handyman's booking as handyman")

    return await complete_booking_as_handyman(booking_id, request_id=request.state.request_id, user_payload=user)


@router.post("/bookings/{booking_id}/reject", response_model=RejectBookingResponse, tags=["Bookings"])
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


@router.post("/bookings/{booking_id}/review", response_model=HandymanReviewResponse, tags=["Bookings"])
async def create_booking_review_endpoint(
    booking_id: str,
    data: CreateHandymanReviewRequest,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["user", "admin"])

    booking = await get_booking(booking_id, request_id=request.state.request_id, user_payload=user)

    if booking.get("status") != "COMPLETED":
        raise HTTPException(status_code=400, detail="Can only review completed bookings")

    if not _has_role(user, "admin") and booking.get("user_email") != _user_email(user):
        raise HTTPException(status_code=403, detail="Cannot review another user's booking")

    return await create_handyman_review(
        {
            "booking_id": booking_id,
            "handyman_email": booking.get("handyman_email"),
            "user_email": booking.get("user_email"),
            "rating": data.rating,
            "review_text": data.review_text,
        },
        request_id=request.state.request_id,
        user_payload=user,
    )


@router.get("/me/bookings", response_model=List[BookingResponse], tags=["Bookings"])
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


@router.get("/me/jobs", response_model=List[BookingResponse], tags=["Bookings"])
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


@router.get("/bookings", tags=["Bookings"])
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


@router.put("/bookings/{booking_id}", tags=["Bookings"])
async def admin_update_booking_endpoint(
    booking_id: str,
    data: UpdateBookingAdmin,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await admin_update_booking(booking_id, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.delete("/bookings/{booking_id}", tags=["Bookings"])
async def admin_delete_booking_endpoint(
    booking_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await admin_delete_booking(booking_id, request_id=request.state.request_id, user_payload=user)
