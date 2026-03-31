from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List

class AvailabilitySlot(BaseModel):
    start: str = Field(..., min_length=1)
    end: str = Field(..., min_length=1)

class SetAvailability(BaseModel):
    slots: List[AvailabilitySlot] = Field(default_factory=list)

class OverlapRequest(BaseModel):
    desired_start: str = Field(..., min_length=1)
    desired_end: str = Field(..., min_length=1)

class AvailabilityMessageResponse(BaseModel):
    message: str

class AvailabilityResponse(BaseModel):
    email: str
    slots: List[AvailabilitySlot] = Field(default_factory=list)

class AvailabilityListItem(BaseModel):
    email: str
    slots: List[AvailabilitySlot] = Field(default_factory=list)

class AvailabilityListResponse(BaseModel):
    cursor: int
    items: List[AvailabilityListItem] = Field(default_factory=list)

class OverlapResponse(BaseModel):
    available: bool