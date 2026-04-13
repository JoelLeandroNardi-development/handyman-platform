from __future__ import annotations
from enum import StrEnum

class BookingStatus(StrEnum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"

class BookingEventType(StrEnum):
    REQUESTED = "booking.requested"
    CONFIRM_REQUESTED = "booking.confirm_requested"
    CANCEL_REQUESTED = "booking.cancel_requested"
    REJECTED = "booking.rejected"
    COMPLETED = "booking.completed"
    COMPLETED_BY_USER = "booking.completed_by_user"
    COMPLETED_BY_HANDYMAN = "booking.completed_by_handyman"

class SlotEventType(StrEnum):
    RESERVED = "slot.reserved"
    REJECTED = "slot.rejected"
    CONFIRMED = "slot.confirmed"
    EXPIRED = "slot.expired"
    RELEASED = "slot.released"

class BookingActor(StrEnum):
    USER = "user"
    HANDYMAN = "handyman"

class EventKey(StrEnum):
    EVENT_ID = "event_id"
    EVENT_TYPE = "event_type"
    DATA = "data"

class DataKey(StrEnum):
    BOOKING_ID = "booking_id"
    USER_EMAIL = "user_email"
    HANDYMAN_EMAIL = "handyman_email"
    DESIRED_START = "desired_start"
    DESIRED_END = "desired_end"
    JOB_DESCRIPTION = "job_description"
    REASON = "reason"

class TableName(StrEnum):
    BOOKINGS = "bookings"

class CancellationReason(StrEnum):
    USER_REQUESTED = "user_requested"
    RELEASED = "released"

class FailureReason(StrEnum):
    SLOT_REJECTED = "slot_rejected"

class ErrorMessage(StrEnum):
    BOOKING_NOT_FOUND = "Booking not found"

class ResponseMessage(StrEnum):
    DELETED = "deleted"

VALID_BOOKING_STATUSES = frozenset(status.value for status in BookingStatus)