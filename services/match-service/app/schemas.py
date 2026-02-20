from pydantic import BaseModel
from typing import Optional


class MatchRequest(BaseModel):
    latitude: float
    longitude: float
    skill: str


class MatchResult(BaseModel):
    email: str
    distance_km: float
    years_experience: int
    availability_unknown: bool = False
