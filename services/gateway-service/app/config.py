import os
from typing import Dict


AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
HANDYMAN_SERVICE_URL = os.getenv("HANDYMAN_SERVICE_URL", "http://handyman-service:8000")
AVAILABILITY_SERVICE_URL = os.getenv("AVAILABILITY_SERVICE_URL", "http://availability-service:8000")
MATCH_SERVICE_URL = os.getenv("MATCH_SERVICE_URL", "http://match-service:8000")
BOOKING_SERVICE_URL = os.getenv("BOOKING_SERVICE_URL", "http://booking-service:8000")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8000")


def SERVICE_BASE_URLS() -> Dict[str, str]:
    """
    Single source of truth for service discovery in the gateway.
    Keys are the canonical service names used in breakers and system endpoints.
    """
    return {
        "auth-service": AUTH_SERVICE_URL,
        "user-service": USER_SERVICE_URL,
        "handyman-service": HANDYMAN_SERVICE_URL,
        "availability-service": AVAILABILITY_SERVICE_URL,
        "match-service": MATCH_SERVICE_URL,
        "booking-service": BOOKING_SERVICE_URL,
        "notification-service": NOTIFICATION_SERVICE_URL,
    }