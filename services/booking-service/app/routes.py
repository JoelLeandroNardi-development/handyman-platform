import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from .db import SessionLocal
from .models import Booking
from .schemas import CreateBooking, BookingResponse, CancelBooking
from .events import build_event, to_json
from .publisher import publisher

router = APIRouter()


@router.post("/bookings", response_model=BookingResponse)
async def create_booking(data: CreateBooking):
    booking_id = str(uuid.uuid4())

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
        await db.commit()

    ev = build_event(
        "booking.requested",
        {
            "booking_id": booking_id,
            "user_email": data.user_email,
            "handyman_email": data.handyman_email,
            "desired_start": data.desired_start,
            "desired_end": data.desired_end,
        },
    )
    await publisher.publish("booking.requested", to_json(ev))

    return BookingResponse(booking_id=booking_id, status="PENDING")


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
            failure_reason=booking.failure_reason,
            cancellation_reason=booking.cancellation_reason,
        )


@router.post("/bookings/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(booking_id: str):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status != "RESERVED":
            raise HTTPException(status_code=400, detail=f"Cannot confirm booking in status {booking.status}")

        ev = build_event(
            "booking.confirm_requested",
            {
                "booking_id": booking.booking_id,
                "handyman_email": booking.handyman_email,
                "desired_start": booking.desired_start,
                "desired_end": booking.desired_end,
            },
        )
        await publisher.publish("booking.confirm_requested", to_json(ev))

        return BookingResponse(booking_id=booking.booking_id, status=booking.status)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(booking_id: str, data: CancelBooking):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status in ("CANCELED", "FAILED", "EXPIRED"):
            # idempotent cancel
            return BookingResponse(
                booking_id=booking.booking_id,
                status=booking.status,
                failure_reason=booking.failure_reason,
                cancellation_reason=booking.cancellation_reason,
            )

        if booking.status == "CONFIRMED":
            # We will mark canceled, but NOT re-add time slot (keeps logic simple)
            booking.status = "CANCELED"
            booking.cancellation_reason = data.reason or "user_requested"
            await db.commit()

            ev = build_event(
                "booking.canceled",
                {
                    "booking_id": booking.booking_id,
                    "reason": booking.cancellation_reason,
                },
            )
            await publisher.publish("booking.canceled", to_json(ev))

            return BookingResponse(
                booking_id=booking.booking_id,
                status=booking.status,
                cancellation_reason=booking.cancellation_reason,
            )

        # PENDING or RESERVED -> release reservation via availability
        booking.status = "CANCELED"
        booking.cancellation_reason = data.reason or "user_requested"
        await db.commit()

        ev = build_event(
            "booking.cancel_requested",
            {
                "booking_id": booking.booking_id,
                "handyman_email": booking.handyman_email,
                "desired_start": booking.desired_start,
                "desired_end": booking.desired_end,
                "reason": booking.cancellation_reason,
            },
        )
        await publisher.publish("booking.cancel_requested", to_json(ev))

        return BookingResponse(
            booking_id=booking.booking_id,
            status=booking.status,
            cancellation_reason=booking.cancellation_reason,
        )