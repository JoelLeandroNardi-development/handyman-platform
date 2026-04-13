from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.constants import BookingActor, BookingEventType, BookingStatus, DataKey, ErrorMessage
from ..domain.events import build_event
from ..domain.models import Booking, OutboxEvent
from ..domain.schemas import CompleteBookingResponse
from shared.core.outbox.helpers import add_outbox_event
from shared.core.db.crud import fetch_or_404

async def complete_booking_side(db: AsyncSession, booking_id: str, *, side: BookingActor) -> CompleteBookingResponse:
    booking = await fetch_or_404(
        db,
        Booking,
        filter_column=Booking.booking_id,
        filter_value=booking_id,
        detail=ErrorMessage.BOOKING_NOT_FOUND,
    )

    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(status_code=400, detail=f"Cannot complete booking in status {booking.status}")

    if side == BookingActor.USER:
        booking.completed_by_user = True
    else:
        booking.completed_by_handyman = True

    event_data = {
        DataKey.BOOKING_ID: booking.booking_id,
        DataKey.USER_EMAIL: booking.user_email,
        DataKey.HANDYMAN_EMAIL: booking.handyman_email,
        DataKey.DESIRED_START: booking.desired_start,
        DataKey.DESIRED_END: booking.desired_end,
        DataKey.JOB_DESCRIPTION: booking.job_description,
    }

    if booking.completed_by_user and booking.completed_by_handyman:
        booking.status = BookingStatus.COMPLETED
        booking.completed_at = datetime.now(timezone.utc)
        event = build_event(BookingEventType.COMPLETED, event_data)
    else:
        event = build_event(
            BookingEventType.COMPLETED_BY_USER if side == BookingActor.USER else BookingEventType.COMPLETED_BY_HANDYMAN,
            event_data,
        )

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