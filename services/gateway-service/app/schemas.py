from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

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

class CreateUser(BaseModel):
    email: str
    full_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class UpdateUserLocation(BaseModel):
    latitude: float
    longitude: float

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

class AvailabilitySlot(BaseModel):
    start: str
    end: str

class SetAvailability(BaseModel):
    slots: List[AvailabilitySlot]

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

# ---- Booking ----

class CreateBookingRequest(BaseModel):
    user_email: str
    handyman_email: str
    desired_start: datetime
    desired_end: datetime

class BookingResponse(BaseModel):
    booking_id: str
    status: str
    user_email: str
    handyman_email: str
    desired_start: datetime
    desired_end: datetime
    failure_reason: Optional[str] = None

class ConfirmBookingResponse(BaseModel):
    booking_id: str
    status: str