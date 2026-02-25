import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal
from .models import MatchLog
from .schemas import MatchRequest
from .services import (
    haversine,
    fetch_handymen,
    is_available,
    availability_service_up,
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
    requested_skill = norm(data.skill)

    availability_up = await availability_service_up()
    degraded = not availability_up

    key = cache_key(data.latitude, data.longitude, requested_skill, degraded=degraded)

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

        distance = haversine(
            data.latitude,
            data.longitude,
            h["latitude"],
            h["longitude"],
        )

        if distance > h["service_radius_km"]:
            continue

        # strict mode: require availability
        if availability_up:
            try:
                available = await is_available(h["email"])
                if not available:
                    continue
                availability_unknown = False
            except Exception:
                # degrade mid-request if availability dies
                availability_up = False
                availability_unknown = True
        else:
            availability_unknown = True

        results.append(
            {
                "email": h["email"],
                "distance_km": round(distance, 2),
                "years_experience": h["years_experience"],
                "availability_unknown": availability_unknown,
            }
        )

    results.sort(key=lambda x: x["distance_km"])

    # bucket-indexed cache
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

    log = MatchLog(
        user_latitude=data.latitude,
        user_longitude=data.longitude,
        skill=requested_skill,
    )
    db.add(log)
    await db.commit()

    return results
