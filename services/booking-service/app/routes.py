import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, delete

from .db import SessionLocal
from .models import Booking, OutboxEvent
from .schemas import (
    CreateBooking,
    BookingResponse,
    CancelBooking,
    CancelBookingResponse,
    ConfirmBookingResponse,
    UpdateBookingAdmin,
    CompleteBookingResponse,
    RejectBookingRequest,
    RejectBookingResponse,
)
from .events import build_event

router = APIRouter()


def _to_response(booking: Booking) -> BookingResponse:
    return BookingResponse(
        booking_id=booking.booking_id,
        status=booking.status,
        user_email=booking.user_email,
        handyman_email=booking.handyman_email,
        desired_start=booking.desired_start,
        desired_end=booking.desired_end,
        job_description=booking.job_description,
        completed_by_user=bool(booking.completed_by_user),
        completed_by_handyman=bool(booking.completed_by_handyman),
        completed_at=booking.completed_at,
        rejected_by_handyman=bool(booking.rejected_by_handyman),
        rejection_reason=booking.rejection_reason,
        failure_reason=booking.failure_reason,
        cancellation_reason=booking.cancellation_reason,
    )


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
            "job_description": data.job_description,
        },
    )

    async with SessionLocal() as db:
        booking = Booking(
            booking_id=booking_id,
            user_email=data.user_email,
            handyman_email=data.handyman_email,
            desired_start=data.desired_start,
            desired_end=data.desired_end,
            job_description=data.job_description,
            status="PENDING",
            completed_by_user=False,
            completed_by_handyman=False,
            rejected_by_handyman=False,
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
        job_description=data.job_description,
        completed_by_user=False,
        completed_by_handyman=False,
        completed_at=None,
        rejected_by_handyman=False,
        rejection_reason=None,
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
        return _to_response(booking)


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
                "job_description": booking.job_description,
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

        if booking.status in ("CANCELED", "FAILED", "EXPIRED", "REJECTED"):
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
                "job_description": booking.job_description,
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


@router.post("/bookings/{booking_id}/complete/user", response_model=CompleteBookingResponse)
async def complete_booking_as_user(booking_id: str):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail=f"Cannot complete booking in status {booking.status}")

        booking.completed_by_user = True

        if booking.completed_by_user and booking.completed_by_handyman:
            booking.status = "COMPLETED"
            booking.completed_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(booking)

        return CompleteBookingResponse(
            booking_id=booking.booking_id,
            status=booking.status,
            completed_by_user=bool(booking.completed_by_user),
            completed_by_handyman=bool(booking.completed_by_handyman),
            completed_at=booking.completed_at,
        )


@router.post("/bookings/{booking_id}/complete/handyman", response_model=CompleteBookingResponse)
async def complete_booking_as_handyman(booking_id: str):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail=f"Cannot complete booking in status {booking.status}")

        booking.completed_by_handyman = True

        if booking.completed_by_user and booking.completed_by_handyman:
            booking.status = "COMPLETED"
            booking.completed_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(booking)

        return CompleteBookingResponse(
            booking_id=booking.booking_id,
            status=booking.status,
            completed_by_user=bool(booking.completed_by_user),
            completed_by_handyman=bool(booking.completed_by_handyman),
            completed_at=booking.completed_at,
        )


@router.post("/bookings/{booking_id}/reject", response_model=RejectBookingResponse)
async def reject_booking(booking_id: str, data: RejectBookingRequest):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status not in ("RESERVED", "CONFIRMED"):
            raise HTTPException(status_code=400, detail=f"Cannot reject booking in status {booking.status}")

        booking.status = "REJECTED"
        booking.rejected_by_handyman = True
        booking.rejection_reason = data.reason

        await db.commit()
        await db.refresh(booking)

        return RejectBookingResponse(
            booking_id=booking.booking_id,
            status=booking.status,
            rejected_by_handyman=bool(booking.rejected_by_handyman),
            rejection_reason=booking.rejection_reason,
            completed_by_user=bool(booking.completed_by_user),
            completed_by_handyman=bool(booking.completed_by_handyman),
        )


@router.get("/bookings", response_model=list[BookingResponse])
async def list_bookings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(default=None),
    user_email: str | None = Query(default=None),
    handyman_email: str | None = Query(default=None),
):
    async with SessionLocal() as db:
        stmt = select(Booking).order_by(Booking.created_at.desc()).limit(limit).offset(offset)

        if status:
            stmt = stmt.where(Booking.status == status)
        if user_email:
            stmt = stmt.where(Booking.user_email == user_email)
        if handyman_email:
            stmt = stmt.where(Booking.handyman_email == handyman_email)

        res = await db.execute(stmt)
        rows = res.scalars().all()
        return [_to_response(b) for b in rows]


@router.put("/bookings/{booking_id}", response_model=BookingResponse)
async def admin_update_booking(booking_id: str, data: UpdateBookingAdmin):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if data.status is not None:
            booking.status = data.status
        if data.failure_reason is not None:
            booking.failure_reason = data.failure_reason
        if data.cancellation_reason is not None:
            booking.cancellation_reason = data.cancellation_reason
        if data.job_description is not None:
            booking.job_description = data.job_description

        await db.commit()
        await db.refresh(booking)
        return _to_response(booking)


@router.delete("/bookings/{booking_id}")
async def admin_delete_booking(booking_id: str):
    async with SessionLocal() as db:
        res = await db.execute(select(Booking).where(Booking.booking_id == booking_id))
        booking = res.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        await db.execute(delete(Booking).where(Booking.booking_id == booking_id))
        await db.commit()
        return {"message": "deleted", "booking_id": booking_id}