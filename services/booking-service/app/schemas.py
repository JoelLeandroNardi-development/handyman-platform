from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CreateBooking(BaseModel):
    user_email: str
    handyman_email: str
    desired_start: datetime
    desired_end: datetime
    job_description: Optional[str] = None


class BookingResponse(BaseModel):
    booking_id: str
    status: str
    user_email: str
    handyman_email: str
    desired_start: datetime
    desired_end: datetime
    job_description: Optional[str] = None
    completed_by_user: bool = False
    completed_by_handyman: bool = False
    completed_at: Optional[datetime] = None
    completion_rejected_by_handyman: bool = False
    completion_rejection_reason: Optional[str] = None
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


class CompleteBookingResponse(BaseModel):
    booking_id: str
    status: str
    completed_by_user: bool
    completed_by_handyman: bool
    completed_at: Optional[datetime] = None


class RejectCompletionRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class RejectCompletionResponse(BaseModel):
    booking_id: str
    status: str
    completion_rejected_by_handyman: bool
    completion_rejection_reason: Optional[str] = None
    completed_by_user: bool = False
    completed_by_handyman: bool = False


class UpdateBookingAdmin(BaseModel):
    status: Optional[str] = None
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    job_description: Optional[str] = None