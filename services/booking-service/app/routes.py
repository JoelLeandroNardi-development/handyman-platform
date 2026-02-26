import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .db import SessionLocal
from .models import Booking
from .schemas import CreateBookingRequest, BookingResponse, ConfirmBookingResponse
from .events import build_event, to_json
from .publisher import publisher

router = APIRouter()

async def get_db():
    async with SessionLocal() as session:
        yield session

@router.post("/bookings", response_model=BookingResponse)
async def create_booking(data: CreateBookingRequest, db: AsyncSession = Depends(get_db)):
    if data.desired_end <= data.desired_start:
        raise HTTPException(status_code=400, detail="desired_end must be after desired_start")

    booking_id = str(uuid.uuid4())

    booking = Booking(
        booking_id=booking_id,
        user_email=data.user_email,
        handyman_email=data.handyman_email,
        desired_start=data.desired_start,
        desired_end=data.desired_end,
        status="PENDING",
        failure_reason=None,
    )
    db.add(booking)
    await db.commit()

    event = build_event(
        "booking.requested",
        {
            "booking_id": booking_id,
            "user_email": data.user_email,
            "handyman_email": data.handyman_email,
            "desired_start": data.desired_start.isoformat(),
            "desired_end": data.desired_end.isoformat(),
        },
    )
    await publisher.publish("booking.requested", to_json(event))

    return BookingResponse(
        booking_id=booking.booking_id,
        status=booking.status,
        user_email=booking.user_email,
        handyman_email=booking.handyman_email,
        desired_start=booking.desired_start,
        desired_end=booking.desired_end,
        failure_reason=booking.failure_reason,
    )

@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    return BookingResponse(
        booking_id=booking.booking_id,
        status=booking.status,
        user_email=booking.user_email,
        handyman_email=booking.handyman_email,
        desired_start=booking.desired_start,
        desired_end=booking.desired_end,
        failure_reason=booking.failure_reason,
    )

@router.post("/bookings/{booking_id}/confirm", response_model=ConfirmBookingResponse)
async def confirm_booking(booking_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "RESERVED":
        raise HTTPException(status_code=409, detail=f"Booking status must be RESERVED, got {booking.status}")

    event = build_event(
        "booking.confirm_requested",
        {
            "booking_id": booking.booking_id,
            "handyman_email": booking.handyman_email,
            "desired_start": booking.desired_start.isoformat(),
            "desired_end": booking.desired_end.isoformat(),
        },
    )
    await publisher.publish("booking.confirm_requested", to_json(event))

    return ConfirmBookingResponse(booking_id=booking.booking_id, status=booking.status)