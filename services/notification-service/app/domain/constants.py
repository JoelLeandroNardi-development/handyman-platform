from __future__ import annotations
from enum import StrEnum

class NotificationCategory(StrEnum):
    BOOKING = "booking"
    CHAT = "chat"
    SYSTEM = "system"

class NotificationPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

class NotificationStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"

class NotificationEntity(StrEnum):
    BOOKING = "booking"

class EventType(StrEnum):
    BOOKING_REQUESTED = "booking.requested"
    BOOKING_CANCEL_REQUESTED = "booking.cancel_requested"
    BOOKING_COMPLETED = "booking.completed"
    BOOKING_REJECTED = "booking.rejected"
    BOOKING_COMPLETED_BY_USER = "booking.completed_by_user"
    BOOKING_COMPLETED_BY_HANDYMAN = "booking.completed_by_handyman"
    SLOT_RESERVED = "slot.reserved"
    SLOT_REJECTED = "slot.rejected"
    SLOT_CONFIRMED = "slot.confirmed"
    SLOT_EXPIRED = "slot.expired"
    SLOT_RELEASED = "slot.released"

class NotificationType(StrEnum):
    JOB_REQUESTED = "job.requested"
    BOOKING_RESERVED = "booking.reserved"
    BOOKING_CONFIRMED = "booking.confirmed"
    JOB_CONFIRMED = "job.confirmed"
    BOOKING_REJECTED = "booking.rejected"
    BOOKING_EXPIRED = "booking.expired"
    BOOKING_CANCELLED = "booking.cancelled"
    JOB_RELEASED = "job.released"
    BOOKING_COMPLETED = "booking.completed"
    JOB_COMPLETED = "job.completed"
    BOOKING_REJECTED_BY_HANDYMAN = "booking.rejected_by_handyman"
    JOB_COMPLETION_REQUESTED = "job.completion_requested"
    BOOKING_COMPLETION_REQUESTED = "booking.completion_requested"
    NOTIFICATION_CREATED = "notification.created"

class ActionPrefix(StrEnum):
    BOOKINGS = "bookings"
    JOBS = "jobs"

class EventKey(StrEnum):
    EVENT_ID = "event_id"
    EVENT_TYPE = "event_type"
    DATA = "data"

class PayloadKey(StrEnum):
    TYPE = "type"
    NOTIFICATION = "notification"
    UNREAD_COUNT = "unread_count"
    OK = "ok"

class DataKey(StrEnum):
    BOOKING_ID = "booking_id"
    USER_EMAIL = "user_email"
    HANDYMAN_EMAIL = "handyman_email"
    DESIRED_START = "desired_start"
    REASON = "reason"

class NotificationTitle(StrEnum):
    NEW_BOOKING_REQUEST = "New booking request"
    TIME_SLOT_RESERVED = "Time slot reserved"
    BOOKING_CONFIRMED = "Booking confirmed"
    NEW_CONFIRMED_JOB = "New confirmed job"
    TIME_SLOT_UNAVAILABLE = "Time slot unavailable"
    RESERVATION_EXPIRED = "Reservation expired"
    BOOKING_CANCELLED = "Booking cancelled"
    JOB_RELEASED = "Job released"
    BOOKING_COMPLETED = "Booking completed"
    JOB_COMPLETED = "Job completed"
    BOOKING_REJECTED = "Booking rejected"
    CUSTOMER_MARKED_JOB_COMPLETE = "Customer marked job as complete"
    HANDYMAN_MARKED_JOB_COMPLETE = "Handyman marked job as complete"

class NotificationBody(StrEnum):
    USER_REQUESTED_BOOKING = "A user requested a booking with you."
    SLOT_TEMP_RESERVED = "Your requested time slot is temporarily reserved."
    BOOKING_CONFIRMED = "Your booking has been confirmed."
    JOB_CONFIRMED = "A booking has been confirmed for you."
    BOOKING_NOT_RESERVED = "That booking request could not be reserved."
    RESERVATION_EXPIRED = "Your temporary reservation expired before confirmation."
    BOOKING_RELEASED = "Your booking reservation was released."
    JOB_RELEASED = "A reservation associated with your schedule was released."
    BOOKING_COMPLETED = "Your booking has been marked as completed."
    JOB_COMPLETED = "A job has been marked as completed."
    BOOKING_REJECTED = "Your booking was rejected by the handyman."
    CUSTOMER_MARKED_JOB_COMPLETE = "The customer has marked this booking as complete. Please confirm your side to close it."
    HANDYMAN_MARKED_JOB_COMPLETE = "Your handyman has marked the job as complete. Please confirm your side to close the booking."

class SseEvent(StrEnum):
    READY = "ready"
    PING = "ping"

class HttpHeader(StrEnum):
    CACHE_CONTROL = "Cache-Control"
    CONNECTION = "Connection"
    X_ACCEL_BUFFERING = "X-Accel-Buffering"
    CACHE_CONTROL_VALUE = "no-cache"
    CONNECTION_VALUE = "keep-alive"
    X_ACCEL_BUFFERING_VALUE = "no"

class ErrorMessage(StrEnum):
    NOTIFICATION_NOT_FOUND = "Notification not found"
    DEVICE_NOT_FOUND = "Device not found"

TABLE_NOTIFICATIONS = "notifications"
TABLE_NOTIFICATION_PREFERENCES = "notification_preferences"
TABLE_PUSH_DEVICES = "push_devices"

COLUMN_USER_EMAIL = "user_email"
COLUMN_EVENT_ID = "event_id"
COLUMN_TYPE = "type"
COLUMN_ENTITY_ID = "entity_id"

INDEX_UQ_NOTIFICATIONS_RECIPIENT_EVENT_TYPE_ENTITY = "uq_notifications_recipient_event_type_entity"

SSE_MEDIA_TYPE = "text/event-stream"
SSE_HEARTBEAT_INTERVAL_SECONDS = 15

QUERY_STATUS_ALIAS = "status"

PREFERENCE_CATEGORY_BOOKING = NotificationCategory.BOOKING
PREFERENCE_CATEGORY_CHAT = NotificationCategory.CHAT