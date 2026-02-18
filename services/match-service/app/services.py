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


async def fetch_handymen():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{HANDYMAN_SERVICE_URL}/handymen")
        response.raise_for_status()
        return response.json()


async def is_available(email: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{AVAILABILITY_SERVICE_URL}/availability/{email}"
        )
        response.raise_for_status()
        data = response.json()
        return len(data.get("slots", [])) > 0


def cache_key(lat, lon, skill):
    return f"match:{lat}:{lon}:{skill}"


async def get_cached_result(key: str):
    cached = await redis_client.get(key)
    return cached


async def set_cache(key: str, value: str):
    await redis_client.set(key, value, ex=60)  # cache 60 sec
