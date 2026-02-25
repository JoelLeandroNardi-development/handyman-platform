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

# ---- Cache bucketing ----
# Grid size in degrees. 0.05 deg latitude ~ 5.55km.
GRID_DEG = float(os.getenv("MATCH_GRID_DEG") or "0.05")


def norm(s: str) -> str:
    return (s or "").strip().lower()


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
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(f"{HANDYMAN_SERVICE_URL}/handymen")
        response.raise_for_status()
        return response.json()


async def fetch_handyman(email: str) -> dict | None:
    """
    Used by event consumer for surgical invalidation (availability.updated gives email only).
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.get(f"{HANDYMAN_SERVICE_URL}/handymen/{email}")
            if r.status_code != 200:
                return None
            return r.json()
    except Exception:
        return None


async def availability_service_up() -> bool:
    try:
        async with httpx.AsyncClient(timeout=AVAILABILITY_HEALTH_TIMEOUT) as client:
            r = await client.get(f"{AVAILABILITY_SERVICE_URL}/health")
            return r.status_code == 200
    except Exception:
        return False


async def is_available(email: str) -> bool:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(f"{AVAILABILITY_SERVICE_URL}/availability/{email}")
        response.raise_for_status()
        data = response.json()
        return len(data.get("slots", [])) > 0


# ---- Cache key + bucket index helpers ----

def bucket_id(lat: float, lon: float) -> tuple[int, int]:
    """
    Convert lat/lon -> integer bucket coordinates so keys are stable.
    """
    b_lat = int(math.floor(lat / GRID_DEG))
    b_lon = int(math.floor(lon / GRID_DEG))
    return b_lat, b_lon


def cache_key(lat: float, lon: float, skill: str, degraded: bool) -> str:
    mode = "degraded" if degraded else "strict"
    b_lat, b_lon = bucket_id(lat, lon)
    return f"match:{mode}:{skill}:lat={b_lat}:lon={b_lon}"


def bucket_set_key(mode: str, skill: str, b_lat: int, b_lon: int) -> str:
    return f"matchkeys:{mode}:{skill}:lat={b_lat}:lon={b_lon}"


async def get_cached_result(key: str):
    return await redis_client.get(key)


async def set_cache_with_index(
    *,
    cache_key_str: str,
    value: str,
    ttl_seconds: int,
    mode: str,
    skill: str,
    b_lat: int,
    b_lon: int,
):
    """
    Store cached result and index it in the bucket set for surgical invalidation.
    """
    set_key = bucket_set_key(mode, skill, b_lat, b_lon)
    pipe = redis_client.pipeline()
    pipe.set(cache_key_str, value, ex=ttl_seconds)
    pipe.sadd(set_key, cache_key_str)
    pipe.expire(set_key, ttl_seconds + 5)  # keep index close to cache TTL
    await pipe.execute()


async def invalidate_bucket(mode: str, skill: str, b_lat: int, b_lon: int) -> int:
    """
    Delete all cached keys registered under a given bucket set.
    Returns number of cache keys deleted (best effort).
    """
    set_key = bucket_set_key(mode, skill, b_lat, b_lon)
    keys = await redis_client.smembers(set_key)
    if not keys:
        # still delete set_key to avoid buildup
        await redis_client.delete(set_key)
        return 0

    pipe = redis_client.pipeline()
    # delete cache keys
    pipe.delete(*list(keys))
    # delete bucket set itself
    pipe.delete(set_key)
    results = await pipe.execute()

    # results[0] is number of deleted cache keys (Redis returns int)
    deleted_cache = results[0] if results and isinstance(results[0], int) else 0
    return deleted_cache


def km_to_deg_lat(km: float) -> float:
    return km / 111.0


def km_to_deg_lon(km: float, lat: float) -> float:
    # avoid division by zero near poles
    c = math.cos(math.radians(lat))
    if abs(c) < 0.01:
        c = 0.01
    return km / (111.0 * c)


def buckets_in_radius(lat: float, lon: float, radius_km: float) -> list[tuple[int, int]]:
    """
    Conservative list of buckets that could intersect a circle around (lat,lon).
    """
    d_lat = km_to_deg_lat(radius_km)
    d_lon = km_to_deg_lon(radius_km, lat)

    lat_min = lat - d_lat
    lat_max = lat + d_lat
    lon_min = lon - d_lon
    lon_max = lon + d_lon

    b_lat_min = int(math.floor(lat_min / GRID_DEG))
    b_lat_max = int(math.floor(lat_max / GRID_DEG))
    b_lon_min = int(math.floor(lon_min / GRID_DEG))
    b_lon_max = int(math.floor(lon_max / GRID_DEG))

    buckets = []
    for b_lat in range(b_lat_min, b_lat_max + 1):
        for b_lon in range(b_lon_min, b_lon_max + 1):
            buckets.append((b_lat, b_lon))
    return buckets
