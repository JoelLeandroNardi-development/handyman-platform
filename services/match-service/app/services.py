import math
import os
import httpx
import redis.asyncio as redis
from datetime import datetime, timezone

HANDYMAN_SERVICE_URL = "http://handyman-service:8000"
AVAILABILITY_SERVICE_URL = "http://availability-service:8000"

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL environment variable is not set")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

HTTP_TIMEOUT = 2.0
AVAILABILITY_HEALTH_TIMEOUT = 0.8

GRID_DEG = float(os.getenv("MATCH_GRID_DEG") or "0.05")
TIME_BUCKET_SECONDS = int(os.getenv("MATCH_TIME_BUCKET_SECONDS") or "900")


def norm(s: str) -> str:
    return (s or "").strip().lower()


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
        r = await client.get(f"{HANDYMAN_SERVICE_URL}/handymen")
        r.raise_for_status()
        return r.json()


async def fetch_handyman(email: str) -> dict | None:
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


async def has_overlapping_availability(email: str, desired_start: datetime, desired_end: datetime) -> bool:
    ds = _as_utc(desired_start).isoformat()
    de = _as_utc(desired_end).isoformat()

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        r = await client.post(
            f"{AVAILABILITY_SERVICE_URL}/availability/{email}/overlap",
            json={"desired_start": ds, "desired_end": de},
        )
        r.raise_for_status()
        return bool(r.json().get("available", False))


def bucket_id(lat: float, lon: float) -> tuple[int, int]:
    return int(math.floor(lat / GRID_DEG)), int(math.floor(lon / GRID_DEG))


def time_bucket(desired_start: datetime) -> int:
    epoch = int(_as_utc(desired_start).timestamp())
    return epoch // TIME_BUCKET_SECONDS


def cache_key(lat: float, lon: float, skill: str, degraded: bool, desired_start: datetime) -> str:
    mode = "degraded" if degraded else "strict"
    b_lat, b_lon = bucket_id(lat, lon)
    t = time_bucket(desired_start)
    return f"match:{mode}:{skill}:lat={b_lat}:lon={b_lon}:t={t}"


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
    set_key = bucket_set_key(mode, skill, b_lat, b_lon)
    pipe = redis_client.pipeline()
    pipe.set(cache_key_str, value, ex=ttl_seconds)
    pipe.sadd(set_key, cache_key_str)
    pipe.expire(set_key, ttl_seconds + 30)
    await pipe.execute()


def km_to_deg_lat(km: float) -> float:
    return km / 111.0


def km_to_deg_lon(km: float, lat: float) -> float:
    c = math.cos(math.radians(lat))
    if abs(c) < 0.01:
        c = 0.01
    return km / (111.0 * c)


def buckets_in_radius(lat: float, lon: float, radius_km: float) -> list[tuple[int, int]]:
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

    out = []
    for bl in range(b_lat_min, b_lat_max + 1):
        for bo in range(b_lon_min, b_lon_max + 1):
            out.append((bl, bo))
    return out


async def invalidate_bucket(mode: str, skill: str, b_lat: int, b_lon: int) -> int:
    mode = norm(mode)
    if mode not in ("strict", "degraded"):
        mode = "strict"

    skill = norm(skill)
    set_key = bucket_set_key(mode, skill, b_lat, b_lon)

    keys = await redis_client.smembers(set_key)
    if not keys:
        await redis_client.delete(set_key)
        return 0

    pipe = redis_client.pipeline()
    pipe.delete(*list(keys))
    pipe.delete(set_key)
    res = await pipe.execute()

    deleted = res[0] if res and isinstance(res[0], int) else 0
    return deleted