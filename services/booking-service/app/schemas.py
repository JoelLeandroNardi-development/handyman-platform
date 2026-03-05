from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CreateBooking(BaseModel):
    user_email: str
    handyman_email: str
    desired_start: datetime
    desired_end: datetime


class BookingResponse(BaseModel):
    booking_id: str
    status: str
    user_email: str
    handyman_email: str
    desired_start: datetime
    desired_end: datetime
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None


class CancelBooking(BaseModel):
    reason: Optional[str] = "user_requested"


class ConfirmBookingResponse(BaseModel):
    booking_id: str
    status: str


class CancelBookingResponse(BaseModel):
    booking_id: str
    status: str
    cancellation_reason: Optional[str] = None


class UpdateBookingAdmin(BaseModel):
    """
    Back-office override. This does NOT emit booking.* domain events
    (to avoid disrupting your existing workflow).
    """
    status: Optional[str] = None
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None