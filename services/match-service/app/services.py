import math
import os
import httpx
import redis.asyncio as redis

HANDYMAN_SERVICE_URL = "http://handyman-service:8000"
AVAILABILITY_SERVICE_URL = "http://availability-service:8000"

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL environment variable is not set")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

HTTP_TIMEOUT = 2.0
AVAILABILITY_HEALTH_TIMEOUT = 0.8


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def norm(s: str) -> str:
    return (s or "").strip().lower()


async def fetch_handymen():
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(f"{HANDYMAN_SERVICE_URL}/handymen")
        response.raise_for_status()
        return response.json()


async def availability_service_up() -> bool:
    """
    Cheap health probe. If it fails, we degrade match behavior.
    """
    try:
        async with httpx.AsyncClient(timeout=AVAILABILITY_HEALTH_TIMEOUT) as client:
            r = await client.get(f"{AVAILABILITY_SERVICE_URL}/health")
            return r.status_code == 200
    except Exception:
        return False


async def is_available(email: str) -> bool:
    """
    Strict check used only when availability-service is up.
    """
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(f"{AVAILABILITY_SERVICE_URL}/availability/{email}")
        response.raise_for_status()
        data = response.json()
        return len(data.get("slots", [])) > 0


def cache_key(lat: float, lon: float, skill: str, degraded: bool) -> str:
    mode = "degraded" if degraded else "strict"
    return f"match:{lat}:{lon}:{skill}:{mode}"


async def get_cached_result(key: str):
    return await redis_client.get(key)


async def set_cache(key: str, value: str, ttl_seconds: int):
    await redis_client.set(key, value, ex=ttl_seconds)
