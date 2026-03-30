from __future__ import annotations

import json
import os
import redis.asyncio as redis

from .cache_keys import bucket_set_key
from ..application.mappers import norm, utc_now_iso
from ..domain.constants import PROJ_HANDYMAN_KEY, PROJ_HANDYMEN_INDEX, PROJ_HANDYMEN_SKILL_INDEX

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL environment variable is not set")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

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
) -> None:
    set_key = bucket_set_key(mode, skill, b_lat, b_lon)
    pipe = redis_client.pipeline()
    pipe.set(cache_key_str, value, ex=ttl_seconds)
    pipe.sadd(set_key, cache_key_str)
    pipe.expire(set_key, ttl_seconds + 30)
    await pipe.execute()