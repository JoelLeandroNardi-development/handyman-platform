import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal
from .models import MatchLog
from .schemas import MatchRequest
from .services import (
    haversine,
    fetch_handymen,
    availability_service_up,
    has_overlapping_availability,
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

    availability_up = await availability_service_up()
    degraded = not availability_up

    key = cache_key(data.latitude, data.longitude, requested_skill, degraded=degraded, desired_start=data.desired_start)
    cached = await get_cached_result(key)
    if cached:
        return json.loads(cached)

    handymen = await fetch_handymen()
    results = []

    for h in handymen:
        skills = [norm(x) for x in (h.get("skills") or [])]
        if requested_skill not in skills:
            continue

        if h.get("latitude") is None or h.get("longitude") is None:
            continue

        distance = haversine(data.latitude, data.longitude, h["latitude"], h["longitude"])
        if distance > h["service_radius_km"]:
            continue

        if availability_up:
            try:
                ok = await has_overlapping_availability(h["email"], data.desired_start, data.desired_end)
                if not ok:
                    continue
                availability_unknown = False
            except Exception:
                availability_up = False
                availability_unknown = True
        else:
            availability_unknown = True

        results.append({
            "email": h["email"],
            "distance_km": round(distance, 2),
            "years_experience": h["years_experience"],
            "availability_unknown": availability_unknown,
        })

    results.sort(key=lambda x: x["distance_km"])

    mode = "strict" if availability_up else "degraded"
    ttl = 60 if availability_up else 15
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