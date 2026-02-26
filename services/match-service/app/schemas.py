from pydantic import BaseModel
from datetime import datetime


class MatchRequest(BaseModel):
    latitude: float
    longitude: float
    skill: str

    # New: desired booking window (ISO datetime strings accepted)
    desired_start: datetime
    desired_end: datetime


class MatchResult(BaseModel):
    email: str
    distance_km: float
    years_experience: int

    # Signal graceful degradation when availability cannot be verified
    availability_unknown: bool = False