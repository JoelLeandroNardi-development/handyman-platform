from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CreateHandyman(BaseModel):
    email: str
    skills: List[str]
    years_experience: int
    service_radius_km: int
    latitude: float | None = None
    longitude: float | None = None


class UpdateLocation(BaseModel):
    latitude: float
    longitude: float


class HandymanResponse(BaseModel):
    email: str
    skills: List[str]
    years_experience: int
    service_radius_km: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime