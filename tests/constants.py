from __future__ import annotations
from enum import StrEnum

class EventType(StrEnum):
    BOOKING_CREATED = "booking.created"
    BOOKING_REQUESTED = "booking.requested"
    BOOKING_CANCEL_REQUESTED = "booking.cancel_requested"
    BOOKING_CONFIRMED = "booking.confirmed"
    BOOKING_CANCELLED = "booking.cancelled"
    BOOKING_COMPLETED = "booking.completed"
    BOOKING_REJECTED = "booking.rejected"
    BOOKING_COMPLETED_BY_USER = "booking.completed_by_user"
    BOOKING_COMPLETED_BY_HANDYMAN = "booking.completed_by_handyman"
    SLOT_RESERVED = "slot.reserved"
    SLOT_REJECTED = "slot.rejected"
    SLOT_CONFIRMED = "slot.confirmed"
    SLOT_EXPIRED = "slot.expired"
    SLOT_RELEASED = "slot.released"
    NOTIFICATION_CREATED = "notification.created"
    JOB_COMPLETED = "job.completed"
    BOOKING_REJECTED_BY_HANDYMAN = "booking.rejected_by_handyman"

class EmailConstants(StrEnum):
    USER = "user@example.com"
    HANDYMAN = "handyman@example.com"
    HANDY = "handy@example.com"
    PRO = "pro@example.com"

ENCODING_UTF8 = "utf-8"
CONTENT_TYPE_JSON = "application/json"

HEADER_RETRY_COUNT = "x-retry-count"
HEADER_ORIGINAL_TIMESTAMP = "x-original-timestamp"

SERVICE_DIRNAME = "services"
APP_DIRNAME = "app"
GATEWAY_SERVICE_DIR = "gateway-service"
PACKAGE_SUFFIX_APP = "_app"

NOTIFICATION_SERVICE_DIR = "notification-service"
NOTIFICATION_SERVICE_PACKAGE = "notification_service_app"
NOTIF_BUILDERS_TEST_PACKAGE = "notif_builders_test_app"
ENV_NOTIFICATION_DB = "NOTIFICATION_DB"
IN_MEMORY_SQLITE_URL = "sqlite+aiosqlite:///:memory:"

EXCHANGE_DOMAIN_EVENTS = "domain_events"
QUEUE_NAME_DEFAULT = "q"
RETRY_QUEUE_NAME_DEFAULT = "q_retry"
DLQ_QUEUE_NAME_DEFAULT = "q_dlq"
ROUTING_KEY_BOOKING_WILDCARD = "booking.*"

RETRY_DELAY_MS = 5000
MAX_RETRIES = 3
PREFETCH_COUNT = 50

EVENT_ID_KEY = "event_id"
EVENT_TYPE_KEY = "event_type"
DATA_KEY = "data"

BOOKING_ID = "booking-123"
JOB_DESCRIPTION_FIX_LEAKY_FAUCET = "Fix leaky faucet"