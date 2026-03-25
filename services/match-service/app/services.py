"""
Services module for match-service.

This module re-exports everything from focused sub-modules and defines the
orchestration functions that compose multiple lower-level operations.

Sub-module responsibilities:
  scoring.py               – ranking weights, norm helpers, datetime utils, scoring math
  geo.py                   – haversine, bucket grid helpers, km-to-degree conversions
  cache_keys.py            – cache key and bucket-set key construction
  projections.py           – Redis client, handyman projection read/list/count/cache ops
  availability_projection.py – availability projection read/delete/count ops
  clients.py               – HTTP client calls to handyman-, availability-, booking-service
"""
from __future__ import annotations

import json

import httpx  # re-exported so tests can patch httpx.AsyncClient via this module

from .scoring import (
    RANKING_WEIGHTS,
    RANKING_CAPS,
    norm,
    _safe_float,
    _safe_int,
    _clamp01,
    utc_now_iso,
    _as_utc,
    parse_dt,
    _distance_score,
    _dampened_count_score,
    compute_match_score,
    rank_match_candidates,
)
from .geo import (
    GRID_DEG,
    TIME_BUCKET_SECONDS,
    haversine,
    bucket_id,
    time_bucket,
    km_to_deg_lat,
    km_to_deg_lon,
    buckets_in_radius,
)
from .cache_keys import cache_key, bucket_set_key
from .projections import (
    redis_client,
    PROJ_HANDYMAN_KEY,
    PROJ_HANDYMEN_INDEX,
    PROJ_HANDYMEN_SKILL_INDEX,
    _normalize_handyman,
    get_handyman_projection,
    list_projected_handymen_by_skill,
    handyman_projection_count,
    invalidate_bucket,
    get_cached_result,
    set_cache_with_index,
)
from .availability_projection import (
    PROJ_AVAIL_KEY,
    PROJ_AVAIL_INDEX,
    _clean_slots,
    get_availability_slots,
    delete_availability_projection,
    projected_has_overlap,
    availability_projection_count,
)
from .clients import (
    HANDYMAN_SERVICE_URL,
    AVAILABILITY_SERVICE_URL,
    BOOKING_SERVICE_URL,
    HTTP_TIMEOUT,
    fetch_handymen_http,
    fetch_availability_http,
    fetch_completed_jobs_counts_batch,
)

# ---------------------------------------------------------------------------
# Orchestration functions
#
# These functions compose multiple lower-level operations and are defined here
# (rather than in sub-modules) so that test-level monkeypatching of their
# dependencies via this module's namespace continues to work correctly.
# ---------------------------------------------------------------------------


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


async def delete_handyman_projection(email: str) -> dict | None:
    if not email:
        return None

    old = await get_handyman_projection(email)
    old_skills = set((old or {}).get("skills") or [])

    pipe = redis_client.pipeline()
    pipe.delete(PROJ_HANDYMAN_KEY.format(email=email))
    pipe.srem(PROJ_HANDYMEN_INDEX, email)
    for s in old_skills:
        pipe.srem(PROJ_HANDYMEN_SKILL_INDEX.format(skill=s), email)
    await pipe.execute()
    return old


async def upsert_availability_projection(*, email: str, slots: list[dict]) -> None:
    if not email:
        return

    clean_slots = _clean_slots(slots)

    if not clean_slots:
        await delete_availability_projection(email)
        return

    payload = {"email": email, "slots": clean_slots, "updated_at": utc_now_iso()}

    pipe = redis_client.pipeline()
    pipe.set(PROJ_AVAIL_KEY.format(email=email), json.dumps(payload))
    pipe.sadd(PROJ_AVAIL_INDEX, email)
    await pipe.execute()


async def hydrate_completed_jobs_counts(handymen: list[dict]) -> list[dict]:
    if not handymen:
        return handymen

    emails = [str(h.get("email")).strip() for h in handymen if isinstance(h, dict) and h.get("email")]
    counts = await fetch_completed_jobs_counts_batch(emails)

    for h in handymen:
        if not isinstance(h, dict):
            continue
        email = h.get("email")
        if isinstance(email, str) and email in counts:
            h["completed_jobs_count"] = counts[email]
            continue
        try:
            h["completed_jobs_count"] = int(h.get("completed_jobs_count") or 0)
        except Exception:
            h["completed_jobs_count"] = 0

    return handymen


async def projections_have_any_availability() -> bool:
    return (await availability_projection_count()) > 0


async def get_effective_availability_slots(email: str) -> tuple[list[dict] | None, str]:
    projected = await get_availability_slots(email)
    if projected is not None:
        return projected, "projection"

    live = await fetch_availability_http(email)
    if live is None:
        return None, "missing"

    await upsert_availability_projection(email=email, slots=live)
    return live, "live"


async def seed_handyman_projection_if_empty() -> dict:
    existing = await handyman_projection_count()
    if existing > 0:
        return {"seeded": False, "reason": "already_present", "count": existing}

    try:
        handymen = await fetch_handymen_http()
    except Exception as e:
        return {"seeded": False, "reason": f"fetch_failed: {type(e).__name__}: {e}", "count": 0}

    ok = 0
    for h in handymen or []:
        try:
            await upsert_handyman_projection(h)
            ok += 1
        except Exception:
            continue

    return {"seeded": True, "reason": "bootstrapped", "count": ok}


async def get_live_handymen_for_skill(skill: str) -> list[dict]:
    skill = norm(skill)
    if not skill:
        return []

    all_handymen = await fetch_handymen_http()
    matched: list[dict] = []

    for h in all_handymen:
        skills = [norm(s) for s in (h.get("skills") or [])]
        if skill in skills:
            matched.append(h)
            try:
                await upsert_handyman_projection(h)
            except Exception:
                pass

    return matched


async def get_effective_handymen_for_skill(skill: str) -> tuple[list[dict], str]:
    skill = norm(skill)
    if not skill:
        return [], "empty-skill"

    projected = await list_projected_handymen_by_skill(skill)
    if projected:
        return projected, "projection"

    live = await get_live_handymen_for_skill(skill)
    return live, "live"