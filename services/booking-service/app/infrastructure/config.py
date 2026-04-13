from __future__ import annotations

from ..domain.constants import SlotEventType

SERVICE_NAME = "booking-service"
SERVICE_VERSION = "0.1.0"

QUEUE_NAME = "booking_service_domain_events"
RETRY_QUEUE_SUFFIX = "_retry"
DLQ_QUEUE_SUFFIX = "_dlq"
RETRY_QUEUE = f"{QUEUE_NAME}{RETRY_QUEUE_SUFFIX}"
DLQ_QUEUE = f"{QUEUE_NAME}{DLQ_QUEUE_SUFFIX}"

ROUTING_KEYS = (
    SlotEventType.RESERVED,
    SlotEventType.REJECTED,
    SlotEventType.CONFIRMED,
    SlotEventType.EXPIRED,
    SlotEventType.RELEASED,
)

DEFAULT_RETRY_DELAY_MS = 5000
DEFAULT_MAX_RETRIES = 3
DEFAULT_PREFETCH = 50
CONSUMER_RECONNECT_WAIT_SECONDS = 5

SERVICE_LOG_PREFIX = f"[{SERVICE_NAME}]"