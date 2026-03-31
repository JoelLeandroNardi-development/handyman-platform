import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers import complete_booking_side
from ..mappers import to_response
from ...domain.constants import VALID_BOOKING_STATUSES
from ...domain.events import build_event
from ...domain.models import Booking, OutboxEvent
from ...domain.schemas import (
    BookingResponse,
    CreateBooking,
    ConfirmBookingResponse,
    CancelBooking,
    CancelBookingResponse,
    CompleteBookingResponse,
    RejectBookingRequest,
    RejectBookingResponse,
    CompletedJobsCountsResponse,
    UpdateBookingAdmin,
    DeleteBookingResponse
)
from ...infrastructure.repository import get_completed_jobs_counts
from shared.core.outbox.helpers import add_outbox_event
from shared.core.db.crud import fetch_or_404

class BookingCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_booking(self, data: CreateBooking) -> BookingResponse:
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
        self.db.add(booking)

        add_outbox_event(self.db, OutboxEvent, event)

        await self.db.commit()
        await self.db.refresh(booking)

        return to_response(booking)

    async def confirm_booking(self, booking_id: str) -> ConfirmBookingResponse:
        booking = await fetch_or_404(self.db, Booking, filter_column=Booking.booking_id, filter_value=booking_id, detail="Booking not found")

        if booking.status != "RESERVED":
            raise HTTPException(status_code=400, detail=f"Cannot confirm booking in status {booking.status}")

        event = build_event(
            "booking.confirm_requested",
            {
                "booking_id": booking.booking_id,
                "user_email": booking.user_email,
                "handyman_email": booking.handyman_email,
                "desired_start": booking.desired_start,
                "desired_end": booking.desired_end,
                "job_description": booking.job_description,
            },
        )

        add_outbox_event(self.db, OutboxEvent, event)

        await self.db.commit()
        return ConfirmBookingResponse(booking_id=booking.booking_id, status=booking.status)

    async def cancel_booking(self, booking_id: str, data: CancelBooking) -> CancelBookingResponse:
        booking = await fetch_or_404(self.db, Booking, filter_column=Booking.booking_id, filter_value=booking_id, detail="Booking not found")

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
                "user_email": booking.user_email,
                "handyman_email": booking.handyman_email,
                "desired_start": booking.desired_start,
                "desired_end": booking.desired_end,
                "job_description": booking.job_description,
                "reason": booking.cancellation_reason,
            },
        )

        add_outbox_event(self.db, OutboxEvent, event)

        await self.db.commit()

        return CancelBookingResponse(
            booking_id=booking.booking_id,
            status=booking.status,
            cancellation_reason=booking.cancellation_reason,
        )

    async def complete_booking_as_user(self, booking_id: str) -> CompleteBookingResponse:
        return await complete_booking_side(self.db, booking_id, side="user")

    async def complete_booking_as_handyman(self, booking_id: str) -> CompleteBookingResponse:
        return await complete_booking_side(self.db, booking_id, side="handyman")

    async def reject_booking(self, booking_id: str, data: RejectBookingRequest) -> RejectBookingResponse:
        booking = await fetch_or_404(self.db, Booking, filter_column=Booking.booking_id, filter_value=booking_id, detail="Booking not found")

        if booking.status not in ("RESERVED", "CONFIRMED"):
            raise HTTPException(status_code=400, detail=f"Cannot reject booking in status {booking.status}")

        booking.status = "REJECTED"
        booking.rejected_by_handyman = True
        booking.rejection_reason = data.reason

        event = build_event(
            "booking.rejected",
            {
                "booking_id": booking.booking_id,
                "user_email": booking.user_email,
                "handyman_email": booking.handyman_email,
                "desired_start": booking.desired_start,
                "desired_end": booking.desired_end,
                "job_description": booking.job_description,
                "reason": data.reason,
            },
        )

        add_outbox_event(self.db, OutboxEvent, event)

        await self.db.commit()
        await self.db.refresh(booking)

        return RejectBookingResponse(
            booking_id=booking.booking_id,
            status=booking.status,
            rejected_by_handyman=bool(booking.rejected_by_handyman),
            rejection_reason=booking.rejection_reason,
            completed_by_user=bool(booking.completed_by_user),
            completed_by_handyman=bool(booking.completed_by_handyman),
        )

    async def completed_counts_batch(self, emails: list[str]) -> CompletedJobsCountsResponse:
        counts = await get_completed_jobs_counts(self.db, emails)
        return {"counts": counts}
    
    async def admin_update_booking(self, booking_id: str, data: UpdateBookingAdmin) -> BookingResponse:
        booking = await fetch_or_404(self.db, Booking, filter_column=Booking.booking_id, filter_value=booking_id, detail="Booking not found")

        if data.status is not None:
            if data.status not in VALID_BOOKING_STATUSES:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid booking status: {data.status!r}. Allowed: {sorted(VALID_BOOKING_STATUSES)}",
                )
            booking.status = data.status
        if data.failure_reason is not None:
            booking.failure_reason = data.failure_reason
        if data.cancellation_reason is not None:
            booking.cancellation_reason = data.cancellation_reason
        if data.job_description is not None:
            booking.job_description = data.job_description

        await self.db.commit()
        await self.db.refresh(booking)
        return to_response(booking)

    async def admin_delete_booking(self, booking_id: str) -> DeleteBookingResponse:
        booking = await fetch_or_404(self.db, Booking, filter_column=Booking.booking_id, filter_value=booking_id, detail="Booking not found")

        await self.db.delete(booking)
        await self.db.commit()
        return {"message": "deleted", "booking_id": booking_id}