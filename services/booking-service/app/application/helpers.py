from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.events import build_event
from ..domain.models import Booking, OutboxEvent
from ..domain.schemas import CompleteBookingResponse
from shared.shared.outbox_helpers import add_outbox_event
from shared.shared.crud_helpers import fetch_or_404

async def _complete_booking_side(db: AsyncSession, booking_id: str, *, side: str) -> CompleteBookingResponse:
    booking = await fetch_or_404(db, Booking, filter_column=Booking.booking_id, filter_value=booking_id, detail="Booking not found")

    if booking.status != "CONFIRMED":
        raise HTTPException(status_code=400, detail=f"Cannot complete booking in status {booking.status}")

    if side == "user":
        booking.completed_by_user = True
    else:
        booking.completed_by_handyman = True

    event_data = {
        "booking_id": booking.booking_id,
        "user_email": booking.user_email,
        "handyman_email": booking.handyman_email,
        "desired_start": booking.desired_start,
        "desired_end": booking.desired_end,
        "job_description": booking.job_description,
    }

    if booking.completed_by_user and booking.completed_by_handyman:
        booking.status = "COMPLETED"
        booking.completed_at = datetime.now(timezone.utc)
        event = build_event("booking.completed", event_data)
    else:
        event = build_event(f"booking.completed_by_{side}", event_data)

    add_outbox_event(db, OutboxEvent, event)

    await db.commit()
    await db.refresh(booking)

    return CompleteBookingResponse(
        booking_id=booking.booking_id,
        status=booking.status,
        completed_by_user=bool(booking.completed_by_user),
        completed_by_handyman=bool(booking.completed_by_handyman),
        completed_at=booking.completed_at,
    )