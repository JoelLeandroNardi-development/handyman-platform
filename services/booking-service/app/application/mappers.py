from ..domain.models import Booking
from ..domain.schemas import BookingResponse

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