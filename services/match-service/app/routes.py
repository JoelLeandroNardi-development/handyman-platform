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
    cache_key,
    get_cached_result,
    set_cache,
)

router = APIRouter()


async def get_db():
    async with SessionLocal() as session:
        yield session


@router.post("/match")
async def match(data: MatchRequest, db: AsyncSession = Depends(get_db)):
    key = cache_key(data.latitude, data.longitude, data.skill)

    cached = await get_cached_result(key)
    if cached:
        return json.loads(cached)

    handymen = await fetch_handymen()
    results = []

    for h in handymen:
        if data.skill not in h["skills"]:
            continue

        if h["latitude"] is None or h["longitude"] is None:
            continue

        distance = haversine(
            data.latitude,
            data.longitude,
            h["latitude"],
            h["longitude"],
        )

        if distance > h["service_radius_km"]:
            continue

        available = await is_available(h["email"])
        if not available:
            continue

        results.append(
            {
                "email": h["email"],
                "distance_km": round(distance, 2),
                "years_experience": h["years_experience"],
            }
        )

    results.sort(key=lambda x: x["distance_km"])

    await set_cache(key, json.dumps(results))

    log = MatchLog(
        user_latitude=data.latitude,
        user_longitude=data.longitude,
        skill=data.skill,
    )
    db.add(log)
    await db.commit()

    return results
