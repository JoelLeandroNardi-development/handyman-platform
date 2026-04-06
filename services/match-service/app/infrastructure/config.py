import os

QUEUE_NAME = "match_service_domain_events"
RETRY_QUEUE = "match_service_domain_events_retry"
DLQ_QUEUE = "match_service_domain_events_dlq"

ROUTING_KEYS = [
    "availability.updated",
    "handyman.created",
    "handyman.location_updated",
    "handyman.updated",
    "handyman.deleted",
]

MAX_RETRIES = 3
RETRY_DELAY_MS = 5000
IDEMPOTENCY_TTL_SECONDS = 3600
RETRY_SECONDS = 5

HANDYMAN_SERVICE_URL = os.getenv("HANDYMAN_SERVICE_URL", "http://handyman-service:8000")
AVAILABILITY_SERVICE_URL = os.getenv("AVAILABILITY_SERVICE_URL", "http://availability-service:8000")
BOOKING_SERVICE_URL = os.getenv("BOOKING_SERVICE_URL", "http://booking-service:8000")

HTTP_TIMEOUT = 2.0