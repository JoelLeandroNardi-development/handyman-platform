from __future__ import annotations

from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..mappers import log_to_response, norm
from ..services import norm
from ...domain.models import MatchLog
from ...domain.schemas import MatchLogResponse
from shared.core.db.crud import fetch_or_404

class MatchLogQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_match_logs(
        self,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        skill: str | None = Query(default=None),
    ) -> list[MatchLogResponse]:
        stmt = select(MatchLog).order_by(MatchLog.id.desc()).limit(limit).offset(offset)
        if skill:
            stmt = stmt.where(MatchLog.skill == norm(skill))

        res = await self.db.execute(stmt)
        rows = res.scalars().all()
        return [log_to_response(r) for r in rows]

    async def get_match_log(self, log_id: int) -> MatchLogResponse:
        row = await fetch_or_404(self.db, MatchLog, filter_column=MatchLog.id, filter_value=log_id, detail="MatchLog not found")
        return log_to_response(row)