import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from .db import SessionLocal
from .models import Booking, OutboxEvent
from .schemas import (
    CreateBooking,
    BookingResponse,
    CancelBooking,
    CancelBookingResponse,
    ConfirmBookingResponse,
)
from .events import build_event

router = APIRouter()


@router.post("/bookings", response_model=BookingResponse)
async def create_booking(data: CreateBooking):
    booking_id = str(uuid.uuid4())

    event = build_event(
        "booking.requested",
        {
            "booking_id": booking_id,
            "user_email": data.user_email,
            "handyman_email": data.handyman_email,
            "desired_start": data.desired_start,
            "desired_end": data.desired_end,
        },
    )

    async with SessionLocal() as db:
        booking = Booking(
            booking_id=booking_id,
            user_email=data.user_email,
            handyman_email=data.handyman_email,
            desired_start=data.desired_start,
            desired_end=data.desired_end,
            status="PENDING",
        )
        db.add(booking)

        db.add(
            OutboxEvent(
                event_id=event["event_id"],
                event_type=event["event_type"],
                routing_key=event["event_type"],
                payload=event,
                status="PENDING",
            )
        )

        await db.commit()

    return BookingResponse(
        booking_id=booking_id,
        status="PENDING",
        user_email=data.user_email,
        handyman_email=data.handyman_email,
        desired_start=data.desired_start,
        desired_end=data.desired_end,
        failure_reason=None,
        cancellation_reason=None,
    )


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: str):
    async with SessionLocal() as db:
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
            cancellation_reason=booking.cancellation_reason,
        )


@router.post("/bookings/{booking_id}/confirm", response_model=ConfirmBookingResponse)
async def confirm_booking(booking_id: str):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status != "RESERVED":
            raise HTTPException(status_code=400, detail=f"Cannot confirm booking in status {booking.status}")

        event = build_event(
            "booking.confirm_requested",
            {
                "booking_id": booking.booking_id,
                "handyman_email": booking.handyman_email,
                "desired_start": booking.desired_start,
                "desired_end": booking.desired_end,
            },
        )

        db.add(
            OutboxEvent(
                event_id=event["event_id"],
                event_type=event["event_type"],
                routing_key=event["event_type"],
                payload=event,
                status="PENDING",
            )
        )

        await db.commit()
        return ConfirmBookingResponse(booking_id=booking.booking_id, status=booking.status)


@router.post("/bookings/{booking_id}/cancel", response_model=CancelBookingResponse)
async def cancel_booking(booking_id: str, data: CancelBooking):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status in ("CANCELED", "FAILED", "EXPIRED"):
            return CancelBookingResponse(
                booking_id=booking.booking_id,
                status=booking.status,
                cancellation_reason=booking.cancellation_reason,
            )

        booking.status = "CANCELED"
        booking.cancellation_reason = data.reason or "user_requested"
        booking.canceled_at = datetime.now(timezone.utc)

        event = build_event(
            "booking.cancel_requested",
            {
                "booking_id": booking.booking_id,
                "handyman_email": booking.handyman_email,
                "desired_start": booking.desired_start,
                "desired_end": booking.desired_end,
                "reason": booking.cancellation_reason,
            },
        )

        db.add(
            OutboxEvent(
                event_id=event["event_id"],
                event_type=event["event_type"],
                routing_key=event["event_type"],
                payload=event,
                status="PENDING",
            )
        )

        await db.commit()

        return CancelBookingResponse(
            booking_id=booking.booking_id,
            status=booking.status,
            cancellation_reason=booking.cancellation_reason,
        )