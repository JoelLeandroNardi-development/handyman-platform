from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CreateUser(BaseModel):
    email: str
    full_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UpdateLocation(BaseModel):
    latitude: float
    longitude: float


class UpdateUser(BaseModel):
    full_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UserResponse(BaseModel):
    email: str
    full_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime