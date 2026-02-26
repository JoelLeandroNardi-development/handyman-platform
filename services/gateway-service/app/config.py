import os

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
HANDYMAN_SERVICE_URL = os.getenv("HANDYMAN_SERVICE_URL", "http://handyman-service:8000")
AVAILABILITY_SERVICE_URL = os.getenv("AVAILABILITY_SERVICE_URL", "http://availability-service:8000")
MATCH_SERVICE_URL = os.getenv("MATCH_SERVICE_URL", "http://match-service:8000")
BOOKING_SERVICE_URL = os.getenv("BOOKING_SERVICE_URL", "http://booking-service:8000")