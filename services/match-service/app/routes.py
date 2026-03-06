from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from .db import SessionLocal
from .models import MatchLog
from .schemas import MatchRequest, MatchLogResponse, UpdateMatchLog
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


def _log_to_response(row: MatchLog) -> MatchLogResponse:
    return MatchLogResponse(
        id=row.id,
        user_latitude=row.user_latitude,
        user_longitude=row.user_longitude,
        skill=row.skill,
    )


@router.post("/match")
async def match(data: MatchRequest, db: AsyncSession = Depends(get_db)):
    if data.desired_end <= data.desired_start:
        return []

    requested_skill = norm(data.skill)
    if not requested_skill:
        return []

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

    handymen = await list_projected_handymen_by_skill(requested_skill)

    results: list[dict] = []

    for h in handymen:
        if h.get("latitude") is None or h.get("longitude") is None:
            continue

        distance = haversine(data.latitude, data.longitude, h["latitude"], h["longitude"])
        if distance > (h.get("service_radius_km") or 0):
            continue

        slots = await get_availability_slots(h["email"])

        if slots is None:
            availability_unknown = True
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
                "latitude": h["latitude"],
                "longitude": h["longitude"],
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


@router.get("/match-logs", response_model=list[MatchLogResponse])
async def list_match_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    skill: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MatchLog).order_by(MatchLog.id.desc()).limit(limit).offset(offset)
    if skill:
        stmt = stmt.where(MatchLog.skill == norm(skill))

    res = await db.execute(stmt)
    rows = res.scalars().all()
    return [_log_to_response(r) for r in rows]


@router.get("/match-logs/{log_id}", response_model=MatchLogResponse)
async def get_match_log(log_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MatchLog).where(MatchLog.id == log_id))
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MatchLog not found")
    return _log_to_response(row)


@router.put("/match-logs/{log_id}", response_model=MatchLogResponse)
async def update_match_log(log_id: int, data: UpdateMatchLog, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MatchLog).where(MatchLog.id == log_id))
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MatchLog not found")

    if data.user_latitude is not None:
        row.user_latitude = data.user_latitude
    if data.user_longitude is not None:
        row.user_longitude = data.user_longitude
    if data.skill is not None:
        row.skill = norm(data.skill)

    await db.commit()
    await db.refresh(row)
    return _log_to_response(row)


@router.delete("/match-logs/{log_id}")
async def delete_match_log(log_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MatchLog).where(MatchLog.id == log_id))
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MatchLog not found")

    await db.execute(delete(MatchLog).where(MatchLog.id == log_id))
    await db.commit()
    return {"message": "deleted", "id": log_id}


@router.delete("/match-logs")
async def clear_match_logs(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(MatchLog))
    await db.commit()
    return {"message": "cleared"}