from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from ..mappers import norm, log_to_response
from ...domain.models import MatchLog
from ...domain.schemas import MatchLogResponse, UpdateMatchLog
from shared.core.db.crud import fetch_or_404

class MatchLogCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_match_log(self, log_id: int, data: UpdateMatchLog) -> MatchLogResponse:
        row = await fetch_or_404(self.db, MatchLog, filter_column=MatchLog.id, filter_value=log_id, detail="MatchLog not found")

        if data.user_latitude is not None:
            row.user_latitude = data.user_latitude
        if data.user_longitude is not None:
            row.user_longitude = data.user_longitude
        if data.skill is not None:
            row.skill = norm(data.skill)
        if data.job_description is not None:
            row.job_description = data.job_description

        await self.db.commit()
        await self.db.refresh(row)
        return log_to_response(row)

    async def delete_match_log(self, log_id: int) -> dict:
        row = await fetch_or_404(self.db, MatchLog, filter_column=MatchLog.id, filter_value=log_id, detail="MatchLog not found")

        await self.db.execute(delete(MatchLog).where(MatchLog.id == log_id))
        await self.db.commit()
        return {"message": "deleted", "id": log_id}

    async def clear_match_logs(self) -> dict:
        await self.db.execute(delete(MatchLog))
        await self.db.commit()
        return {"message": "cleared"}