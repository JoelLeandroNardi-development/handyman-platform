from pydantic import BaseModel, Field
from typing import List, Optional


# ---------- AUTH ----------

_ALLOWED_ROLES = {"user", "handyman", "admin"}


class Register(BaseModel):
    email: str
    password: str
    roles: List[str] = Field(default_factory=lambda: ["user"])

    def model_post_init(self, __context):
        normalized = []
        for r in self.roles:
            rr = (r or "").strip().lower()
            if rr not in _ALLOWED_ROLES:
                raise ValueError(f"Invalid role: {r}. Allowed: {sorted(_ALLOWED_ROLES)}")
            if rr not in normalized:
                normalized.append(rr)

        if not normalized:
            normalized = ["user"]

        object.__setattr__(self, "roles", normalized)


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
    availability_unknown: bool = False
