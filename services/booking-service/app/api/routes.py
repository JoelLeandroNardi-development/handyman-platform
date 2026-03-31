from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.commands.booking_command_service import BookingCommandService
from ..application.queries.booking_query_service import BookingQueryService
from ..domain.schemas import (
    BookingResponse,
    CreateBooking,
    ConfirmBookingResponse,
    CancelBooking,
    CancelBookingResponse,
    CompleteBookingResponse,
    RejectBookingRequest,
    RejectBookingResponse,
    CompletedJobsCountResponse,
    CompletedJobsCountsResponse,
    UpdateBookingAdmin,
    DeleteBookingResponse
)
from ..infrastructure.db import SessionLocal
from shared.shared.db import make_get_db

router = APIRouter()
get_db = make_get_db(SessionLocal)

@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: str, db: AsyncSession = Depends(get_db)) -> BookingResponse:
    return await BookingQueryService(db).get_booking(booking_id)

@router.get("/bookings", response_model=list[BookingResponse])
async def list_bookings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(default=None),
    user_email: str | None = Query(default=None),
    handyman_email: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    return await BookingQueryService(db).list_bookings(limit, offset, status, user_email, handyman_email)

@router.get("/bookings/completed-count/{handyman_email}", response_model=CompletedJobsCountResponse)
async def completed_count_for_handyman(handyman_email: str, db: AsyncSession = Depends(get_db)):
    return await BookingQueryService(db).completed_count_for_handyman(handyman_email)

@router.post("/bookings", response_model=BookingResponse)
async def create_booking(data: CreateBooking, db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).create_booking(data)

@router.post("/bookings/{booking_id}/confirm", response_model=ConfirmBookingResponse)
async def confirm_booking(booking_id: str, db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).confirm_booking(booking_id)

@router.post("/bookings/{booking_id}/cancel", response_model=CancelBookingResponse)
async def cancel_booking(booking_id: str, data: CancelBooking, db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).cancel_booking(booking_id, data)

@router.post("/bookings/{booking_id}/complete/user", response_model=CompleteBookingResponse)
async def complete_booking_as_user(booking_id: str, db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).complete_booking_as_user(booking_id)

@router.post("/bookings/{booking_id}/complete/handyman", response_model=CompleteBookingResponse)
async def complete_booking_as_handyman(booking_id: str, db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).complete_booking_as_handyman(booking_id)

@router.post("/bookings/{booking_id}/reject", response_model=RejectBookingResponse)
async def reject_booking(booking_id: str, data: RejectBookingRequest, db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).reject_booking(booking_id, data)

@router.post("/bookings/completed-counts", response_model=CompletedJobsCountsResponse)
async def completed_counts_batch(emails: list[str], db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).completed_counts_batch(emails)

@router.put("/bookings/{booking_id}", response_model=BookingResponse)
async def admin_update_booking(booking_id: str, data: UpdateBookingAdmin, db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).admin_update_booking(booking_id, data)

@router.delete("/bookings/{booking_id}", response_model=DeleteBookingResponse)
async def admin_delete_booking(booking_id: str, db: AsyncSession = Depends(get_db)):
    return await BookingCommandService(db).admin_delete_booking(booking_id)