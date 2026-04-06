from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..match_orchestrator import run_match_query
from ...domain.models import MatchLog
from ...domain.schemas import MatchRequest
from shared.core.utils.normalize import norm

class MatchCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def match(self, data: MatchRequest) -> list[dict]:
        if data.desired_end <= data.desired_start:
            return []

        results = await run_match_query(
            latitude=data.latitude,
            longitude=data.longitude,
            skill=data.skill,
            desired_start=data.desired_start,
            desired_end=data.desired_end,
        )

        self.db.add(
            MatchLog(
                user_latitude=data.latitude,
                user_longitude=data.longitude,
                skill=norm(data.skill),
                job_description=data.job_description,
            )
        )
        await self.db.commit()

        return results