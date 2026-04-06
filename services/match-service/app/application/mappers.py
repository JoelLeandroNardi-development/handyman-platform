from __future__ import annotations

from ..domain.models import MatchLog
from ..domain.schemas import MatchLogResponse

def log_to_response(row: MatchLog) -> MatchLogResponse:
    return MatchLogResponse(
        id=row.id,
        user_latitude=row.user_latitude,
        user_longitude=row.user_longitude,
        skill=row.skill,
        job_description=row.job_description,
    )