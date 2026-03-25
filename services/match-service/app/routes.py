from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from .db import SessionLocal
from .models import MatchLog
from .schemas import MatchRequest, MatchLogResponse, UpdateMatchLog
from shared.shared.crud_helpers import fetch_or_404
from .services import norm
from .match_orchestrator import run_match_query

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
        job_description=row.job_description,
    )


@router.post("/match")
async def match(data: MatchRequest, db: AsyncSession = Depends(get_db)):
    if data.desired_end <= data.desired_start:
        return []

    results = await run_match_query(
        latitude=data.latitude,
        longitude=data.longitude,
        skill=data.skill,
        desired_start=data.desired_start,
        desired_end=data.desired_end,
    )

    db.add(
        MatchLog(
            user_latitude=data.latitude,
            user_longitude=data.longitude,
            skill=norm(data.skill),
            job_description=data.job_description,
        )
    )
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
    row = await fetch_or_404(db, MatchLog, filter_column=MatchLog.id, filter_value=log_id, detail="MatchLog not found")
    return _log_to_response(row)


@router.put("/match-logs/{log_id}", response_model=MatchLogResponse)
async def update_match_log(log_id: int, data: UpdateMatchLog, db: AsyncSession = Depends(get_db)):
    row = await fetch_or_404(db, MatchLog, filter_column=MatchLog.id, filter_value=log_id, detail="MatchLog not found")

    if data.user_latitude is not None:
        row.user_latitude = data.user_latitude
    if data.user_longitude is not None:
        row.user_longitude = data.user_longitude
    if data.skill is not None:
        row.skill = norm(data.skill)
    if data.job_description is not None:
        row.job_description = data.job_description

    await db.commit()
    await db.refresh(row)
    return _log_to_response(row)


@router.delete("/match-logs/{log_id}")
async def delete_match_log(log_id: int, db: AsyncSession = Depends(get_db)):
    row = await fetch_or_404(db, MatchLog, filter_column=MatchLog.id, filter_value=log_id, detail="MatchLog not found")

    await db.execute(delete(MatchLog).where(MatchLog.id == log_id))
    await db.commit()
    return {"message": "deleted", "id": log_id}


@router.delete("/match-logs")
async def clear_match_logs(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(MatchLog))
    await db.commit()
    return {"message": "cleared"}