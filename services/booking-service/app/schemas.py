from pydantic import BaseModel
from typing import Optional


class CreateBooking(BaseModel):
    user_email: str
    handyman_email: str
    desired_start: str
    desired_end: str


class BookingResponse(BaseModel):
    booking_id: str
    status: str
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None


class ConfirmBooking(BaseModel):
    pass


class CancelBooking(BaseModel):
    reason: Optional[str] = "user_requested"