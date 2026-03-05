from pydantic import BaseModel
from datetime import datetime
from typing import Optional


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


class MatchLogResponse(BaseModel):
    id: int
    user_latitude: float
    user_longitude: float
    skill: str


class UpdateMatchLog(BaseModel):
    user_latitude: Optional[float] = None
    user_longitude: Optional[float] = None
    skill: Optional[str] = None