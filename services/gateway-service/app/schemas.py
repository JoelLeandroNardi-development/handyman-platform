from pydantic import BaseModel
from typing import List, Optional


# ---------- AUTH ----------

class Register(BaseModel):
    email: str
    password: str


class Login(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str


# ---------- USER ----------

class CreateUser(BaseModel):
    email: str
    full_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UpdateUserLocation(BaseModel):
    latitude: float
    longitude: float


# ---------- HANDYMAN ----------

class CreateHandyman(BaseModel):
    email: str
    skills: List[str]
    years_experience: int
    service_radius_km: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UpdateHandymanLocation(BaseModel):
    latitude: float
    longitude: float


# ---------- AVAILABILITY ----------

class AvailabilitySlot(BaseModel):
    start: str
    end: str


class SetAvailability(BaseModel):
    slots: List[AvailabilitySlot]


# ---------- MATCH ----------

class MatchRequest(BaseModel):
    latitude: float
    longitude: float
    skill: str


class MatchResult(BaseModel):
    email: str
    distance_km: float
    years_experience: int
