import os

RANKING_WEIGHTS = {
    "distance": 0.42,
    "avg_rating": 0.24,
    "availability_confidence": 0.12,
    "profile_completeness": 0.10,
    "rating_count": 0.06,
    "completed_jobs_count": 0.05,
    "years_experience": 0.01,
}

RANKING_CAPS = {
    "rating_count": 50,
    "completed_jobs_count": 100,
    "years_experience": 30,
}

PROJ_AVAIL_KEY = "proj:availability:{email}"
PROJ_AVAIL_INDEX = "proj:availability:index"

PROJ_HANDYMAN_KEY = "proj:handyman:{email}"
PROJ_HANDYMEN_INDEX = "proj:handymen:index"
PROJ_HANDYMEN_SKILL_INDEX = "proj:handymen:skill:{skill}"

GRID_DEG = float(os.getenv("MATCH_GRID_DEG") or "0.05")
TIME_BUCKET_SECONDS = int(os.getenv("MATCH_TIME_BUCKET_SECONDS") or "900")

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