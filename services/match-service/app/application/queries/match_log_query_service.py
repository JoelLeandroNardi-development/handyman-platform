from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...application.mappers import log_to_response
from ...domain.models import MatchLog
from ...domain.schemas import MatchLogResponse
from shared.core.db.crud import fetch_or_404
from shared.core.utils.normalize import norm

class MatchLogQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_match_logs(
        self,
        limit: int,
        offset: int,
        skill: str | None,
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