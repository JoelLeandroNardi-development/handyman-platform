from __future__ import annotations
from enum import StrEnum

class BookingEventType(StrEnum):
    REQUESTED = "booking.requested"
    CONFIRM_REQUESTED = "booking.confirm_requested"
    CANCEL_REQUESTED = "booking.cancel_requested"

class AvailabilityEventType(StrEnum):
    UPDATED = "availability.updated"

class SlotEventType(StrEnum):
    RESERVED = "slot.reserved"
    REJECTED = "slot.rejected"
    CONFIRMED = "slot.confirmed"
    EXPIRED = "slot.expired"
    RELEASED = "slot.released"

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
    EMAIL = "email"
    SLOTS = "slots"
    REASON = "reason"
    START = "start"
    END = "end"
    CREATED_AT = "created_at"

class RejectionReason(StrEnum):
    NO_MATCHING_SLOT = "no_matching_slot"
    SLOT_CONFLICT_RESERVED = "slot_conflict_reserved"
    RESERVATION_MISSING = "reservation_missing"

RESERVATION_KEY_PREFIX = "reservation"
HANDYMAN_RESERVATION_SET_PREFIX = "reservations_by_handyman"
AVAILABILITY_KEY_PREFIX = "availability"
EXPIRY_ZSET = "reservation_expiry"
RAW_SLOT_SEPARATOR = "|"