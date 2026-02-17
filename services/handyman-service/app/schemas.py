from pydantic import BaseModel
from typing import List


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
