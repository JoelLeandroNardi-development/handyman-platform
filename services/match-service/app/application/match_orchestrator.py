from __future__ import annotations

import json
from datetime import datetime

from .services import (
    get_effective_handymen_for_skill,
    hydrate_completed_jobs_counts,
    get_effective_availability_slots,
    projections_have_any_availability,
)
from ..domain.geo import haversine, bucket_id
from ..domain.constants import CacheMode
from ..domain.scoring import rank_match_candidates
from ..infrastructure.config import CACHE_TTL_DEGRADED_SECONDS, CACHE_TTL_STRICT_SECONDS
from ..infrastructure.availability_projection import projected_has_overlap
from ..infrastructure.cache_keys import cache_key
from ..infrastructure.projections import get_cached_result, set_cache_with_index
from shared.core.utils.normalize import norm

async def run_match_query(
    latitude: float,
    longitude: float,
    skill: str,
    desired_start: datetime,
    desired_end: datetime,
) -> list[dict]:
    requested_skill = norm(skill)
    if not requested_skill:
        return []

    has_any_avail = await projections_have_any_availability()
    degraded = not has_any_avail

    key = cache_key(
        latitude,
        longitude,
        requested_skill,
        degraded=degraded,
        desired_start=desired_start,
    )

    cached = await get_cached_result(key)
    if cached:
        try:
            parsed = json.loads(cached)
            if isinstance(parsed, list) and parsed:
                return parsed
        except Exception:
            pass

    # --- Projection-first: prefer projected handymen; live fetch is a fallback ---
    handymen, _handyman_source = await get_effective_handymen_for_skill(requested_skill)
    handymen = await hydrate_completed_jobs_counts(handymen)

    results: list[dict] = []

    for h in handymen:
        if h.get("latitude") is None or h.get("longitude") is None:
            continue

        distance = haversine(
            float(latitude),
            float(longitude),
            float(h["latitude"]),
            float(h["longitude"]),
        )

        if distance > float(h.get("service_radius_km") or 0):
            continue

        slots, source = await get_effective_availability_slots(h["email"])

        if slots is None:
            availability_unknown = True
            if not degraded:
                continue
        else:
            ok = projected_has_overlap(slots, desired_start, desired_end)
            if not ok:
                continue
            availability_unknown = False

        results.append(
            {
                "email": h["email"],
                "latitude": h["latitude"],
                "longitude": h["longitude"],
                "distance_km": round(distance, 2),
                "years_experience": h.get("years_experience"),
                "availability_unknown": availability_unknown,
                "availability_source": source,
                "avg_rating": h.get("avg_rating", 0),
                "rating_count": h.get("rating_count", 0),
                "profile_completeness": h.get("profile_completeness", 0),
                "completed_jobs_count": h.get("completed_jobs_count", 0),
            }
        )

    results = rank_match_candidates(results)

    mode = CacheMode.DEGRADED if degraded else CacheMode.STRICT
    ttl = CACHE_TTL_DEGRADED_SECONDS if degraded else CACHE_TTL_STRICT_SECONDS
    b_lat, b_lon = bucket_id(latitude, longitude)

    if results:
        await set_cache_with_index(
            cache_key_str=key,
            value=json.dumps(results),
            ttl_seconds=ttl,
            mode=mode,
            skill=requested_skill,
            b_lat=b_lat,
            b_lon=b_lon,
        )

    return results