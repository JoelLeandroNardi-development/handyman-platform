from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
import redis.asyncio as redis
from dateutil import parser

HANDYMAN_SERVICE_URL = os.getenv("HANDYMAN_SERVICE_URL", "http://handyman-service:8000")
AVAILABILITY_SERVICE_URL = os.getenv("AVAILABILITY_SERVICE_URL", "http://availability-service:8000")

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL environment variable is not set")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

HTTP_TIMEOUT = 2.0

GRID_DEG = float(os.getenv("MATCH_GRID_DEG") or "0.05")
TIME_BUCKET_SECONDS = int(os.getenv("MATCH_TIME_BUCKET_SECONDS") or "900")

# ---- Projection keys ----
PROJ_HANDYMAN_KEY = "proj:handyman:{email}"
PROJ_HANDYMEN_INDEX = "proj:handymen:index" 
PROJ_HANDYMEN_SKILL_INDEX = "proj:handymen:skill:{skill}"   

PROJ_AVAIL_KEY = "proj:availability:{email}"
PROJ_AVAIL_INDEX = "proj:availability:index"


# Utilities
def norm(s: str) -> str:
    return (s or "").strip().lower()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_dt(x: Any) -> datetime:
    """
    Parse datetime coming from:
      - already a datetime
      - ISO string
    """
    if isinstance(x, datetime):
        return _as_utc(x)
    if isinstance(x, str):
        return _as_utc(parser.isoparse(x))
    raise ValueError(f"Unsupported datetime type: {type(x).__name__}")


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and a_end > b_start


# Distance + bucketing
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


# Match cache invalidation
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


# Projections: Handyman
def _normalize_handyman(doc: dict) -> dict:
    email = (doc or {}).get("email")
    if not email:
        return {}

    skills = doc.get("skills") or []
    skills_norm = [norm(s) for s in skills if s]
    seen = set()
    skills_norm = [s for s in skills_norm if not (s in seen or seen.add(s))]

    out = {
        "email": email,
        "skills": skills_norm,
        "years_experience": doc.get("years_experience"),
        "service_radius_km": doc.get("service_radius_km"),
        "latitude": doc.get("latitude"),
        "longitude": doc.get("longitude"),
        "updated_at": utc_now_iso(),
    }
    return out


async def get_handyman_projection(email: str) -> dict | None:
    if not email:
        return None
    raw = await redis_client.get(PROJ_HANDYMAN_KEY.format(email=email))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def upsert_handyman_projection(doc: dict) -> None:
    normalized = _normalize_handyman(doc)
    email = normalized.get("email")
    if not email:
        return

    old = await get_handyman_projection(email)
    old_skills = set((old or {}).get("skills") or [])

    new_skills = set(normalized.get("skills") or [])

    pipe = redis_client.pipeline()
    pipe.set(PROJ_HANDYMAN_KEY.format(email=email), json.dumps(normalized))
    pipe.sadd(PROJ_HANDYMEN_INDEX, email)

    for s in (old_skills - new_skills):
        pipe.srem(PROJ_HANDYMEN_SKILL_INDEX.format(skill=s), email)

    for s in new_skills:
        pipe.sadd(PROJ_HANDYMEN_SKILL_INDEX.format(skill=s), email)

    await pipe.execute()


async def list_projected_handymen_by_skill(skill: str) -> list[dict]:
    skill = norm(skill)
    if not skill:
        return []

    emails = await redis_client.smembers(PROJ_HANDYMEN_SKILL_INDEX.format(skill=skill))
    if not emails:
        return []

    pipe = redis_client.pipeline()
    for e in emails:
        pipe.get(PROJ_HANDYMAN_KEY.format(email=e))
    raws = await pipe.execute()

    out: list[dict] = []
    for raw in raws:
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except Exception:
            continue

    return out


async def handyman_projection_count() -> int:
    try:
        return int(await redis_client.scard(PROJ_HANDYMEN_INDEX))
    except Exception:
        return 0


# Projections: Availability
async def upsert_availability_projection(*, email: str, slots: list[dict]) -> None:
    if not email:
        return

    clean_slots: list[dict] = []
    for s in (slots or []):
        if not isinstance(s, dict):
            continue
        start = s.get("start")
        end = s.get("end")
        if not start or not end:
            continue
        try:
            parse_dt(start)
            parse_dt(end)
        except Exception:
            continue
        clean_slots.append({"start": start, "end": end})

    payload = {"email": email, "slots": clean_slots, "updated_at": utc_now_iso()}

    pipe = redis_client.pipeline()
    pipe.set(PROJ_AVAIL_KEY.format(email=email), json.dumps(payload))
    pipe.sadd(PROJ_AVAIL_INDEX, email)
    await pipe.execute()


async def get_availability_slots(email: str) -> list[dict] | None:
    if not email:
        return None
    raw = await redis_client.get(PROJ_AVAIL_KEY.format(email=email))
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj.get("slots") or []
    except Exception:
        return None


def projected_has_overlap(slots: list[dict], desired_start: datetime, desired_end: datetime) -> bool:
    ds = _as_utc(desired_start)
    de = _as_utc(desired_end)

    for slot in (slots or []):
        try:
            ss = parse_dt(slot.get("start"))
            ee = parse_dt(slot.get("end"))
        except Exception:
            continue

        if overlaps(ss, ee, ds, de):
            return True

    return False


async def availability_projection_count() -> int:
    try:
        return int(await redis_client.scard(PROJ_AVAIL_INDEX))
    except Exception:
        return 0


async def projections_have_any_availability() -> bool:
    return (await availability_projection_count()) > 0


# Bootstrap seed (one-time)
async def fetch_handymen_http() -> list[dict]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        r = await client.get(f"{HANDYMAN_SERVICE_URL}/handymen")
        r.raise_for_status()
        return r.json()


async def seed_handyman_projection_if_empty() -> dict:
    """
    Best-effort:
      - if projection is empty, fetch /handymen once and upsert each
      - returns status dict for logging / health
    """
    existing = await handyman_projection_count()
    if existing > 0:
        return {"seeded": False, "reason": "already_present", "count": existing}

    try:
        handymen = await fetch_handymen_http()
    except Exception as e:
        return {"seeded": False, "reason": f"fetch_failed: {type(e).__name__}: {e}", "count": 0}

    ok = 0
    for h in (handymen or []):
        try:
            await upsert_handyman_projection(h)
            ok += 1
        except Exception:
            continue

    return {"seeded": True, "reason": "bootstrapped", "count": ok}

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