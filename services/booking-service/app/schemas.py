from pydantic import BaseModel
from datetime import datetime

class CreateBookingRequest(BaseModel):
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
    failure_reason: str | None = None

class ConfirmBookingResponse(BaseModel):
    booking_id: str
    status: str