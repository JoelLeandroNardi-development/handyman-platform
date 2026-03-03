from pydantic import BaseModel
from datetime import datetime


class MatchRequest(BaseModel):
    latitude: float
    longitude: float
    skill: str
    desired_start: datetime
    desired_end: datetime


class MatchResult(BaseModel):
    email: str
    distance_km: float
    years_experience: int
    availability_unknown: bool = False