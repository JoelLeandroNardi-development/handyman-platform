from __future__ import annotations

import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal
from .models import MatchLog
from .schemas import MatchRequest
from .services import (
    haversine,
    list_projected_handymen_by_skill,
    get_availability_slots,
    projected_has_overlap,
    projections_have_any_availability,
    cache_key,
    get_cached_result,
    set_cache_with_index,
    norm,
    bucket_id,
)

router = APIRouter()


async def get_db():
    async with SessionLocal() as session:
        yield session


@router.post("/match")
async def match(data: MatchRequest, db: AsyncSession = Depends(get_db)):
    if data.desired_end <= data.desired_start:
        return []

    requested_skill = norm(data.skill)
    if not requested_skill:
        return []

    # degraded if we don't have any availability projections at all (bootstrap / events disabled)
    has_any_avail = await projections_have_any_availability()
    degraded = not has_any_avail

    key = cache_key(
        data.latitude,
        data.longitude,
        requested_skill,
        degraded=degraded,
        desired_start=data.desired_start,
    )
    cached = await get_cached_result(key)
    if cached:
        return json.loads(cached)

    # Projection-first candidate retrieval by skill (no Handyman-service call)
    handymen = await list_projected_handymen_by_skill(requested_skill)

    results: list[dict] = []

    for h in handymen:
        if h.get("latitude") is None or h.get("longitude") is None:
            continue

        distance = haversine(data.latitude, data.longitude, h["latitude"], h["longitude"])
        if distance > (h.get("service_radius_km") or 0):
            continue

        # ---- NO HTTP to availability-service anymore ----
        slots = await get_availability_slots(h["email"])

        if slots is None:
            # no projection yet => degraded behavior for this handyman
            availability_unknown = True
            # In strict mode, we typically filter unknowns out. But since strict/degraded is global here,
            # we keep it consistent: in degraded mode we keep unknowns; in strict mode we drop.
            if not degraded:
                continue
        else:
            ok = projected_has_overlap(slots, data.desired_start, data.desired_end)
            if not ok:
                continue
            availability_unknown = False

        results.append(
            {
                "email": h["email"],
                "distance_km": round(distance, 2),
                "years_experience": h.get("years_experience"),
                "availability_unknown": availability_unknown,
            }
        )

    results.sort(key=lambda x: x["distance_km"])

    mode = "degraded" if degraded else "strict"
    ttl = 15 if degraded else 60
    b_lat, b_lon = bucket_id(data.latitude, data.longitude)

    await set_cache_with_index(
        cache_key_str=key,
        value=json.dumps(results),
        ttl_seconds=ttl,
        mode=mode,
        skill=requested_skill,
        b_lat=b_lat,
        b_lon=b_lon,
    )

    db.add(MatchLog(user_latitude=data.latitude, user_longitude=data.longitude, skill=requested_skill))
    await db.commit()

    return results