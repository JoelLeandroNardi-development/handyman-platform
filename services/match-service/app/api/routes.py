from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.commands.match_command_service import MatchCommandService
from ..application.commands.match_log_command_service import MatchLogCommandService
from ..application.queries.match_log_query_service import MatchLogQueryService
from ..domain.schemas import MatchRequest, MatchLogResponse, UpdateMatchLog
from ..infrastructure.db import SessionLocal
from shared.shared.db import make_get_db

router = APIRouter()
get_db = make_get_db(SessionLocal)

@router.get("/match-logs", response_model=list[MatchLogResponse])
async def list_match_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    skill: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await MatchLogQueryService(db).list_match_logs(limit, offset, skill)

@router.get("/match-logs/{log_id}", response_model=MatchLogResponse)
async def get_match_log(log_id: int, db: AsyncSession = Depends(get_db)):
    return await MatchLogQueryService(db).get_match_log(log_id)

@router.post("/match")
async def match(data: MatchRequest, db: AsyncSession = Depends(get_db)):
    return await MatchCommandService(db).match(data)

@router.put("/match-logs/{log_id}", response_model=MatchLogResponse)
async def update_match_log(log_id: int, data: UpdateMatchLog, db: AsyncSession = Depends(get_db)):
    return await MatchLogCommandService(db).update_match_log(log_id, data)

@router.delete("/match-logs/{log_id}")
async def delete_match_log(log_id: int, db: AsyncSession = Depends(get_db)):
    return await MatchLogCommandService(db).delete_match_log(log_id)

@router.delete("/match-logs")
async def clear_match_logs(db: AsyncSession = Depends(get_db)):
    return await MatchLogCommandService(db).clear_match_logs()