from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MatchRequest(BaseModel):
    latitude: float
    longitude: float
    skill: str
    job_description: Optional[str] = None
    desired_start: datetime
    desired_end: datetime


class MatchResult(BaseModel):
    email: str
    latitude: float
    longitude: float
    distance_km: float
    years_experience: int
    availability_unknown: bool = False
    avg_rating: float = 0
    rating_count: int = 0
    profile_completeness: int = 0
    completed_jobs_count: int = 0


class MatchLogResponse(BaseModel):
    id: int
    user_latitude: float
    user_longitude: float
    skill: str
    job_description: Optional[str] = None


class UpdateMatchLog(BaseModel):
    user_latitude: Optional[float] = None
    user_longitude: Optional[float] = None
    skill: Optional[str] = None
    job_description: Optional[str] = None


class DeleteMatchLogResponse(BaseModel):
    message: str
    id: int
