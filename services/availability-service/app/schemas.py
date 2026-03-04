from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List


class AvailabilitySlot(BaseModel):
    # Keep as strings (ISO), because Availability stores raw slot strings in Redis.
    start: str = Field(..., min_length=1)
    end: str = Field(..., min_length=1)


class SetAvailability(BaseModel):
    # Allow empty list (clear availability via POST with slots=[])
    slots: List[AvailabilitySlot] = Field(default_factory=list)


class OverlapRequest(BaseModel):
    desired_start: str = Field(..., min_length=1)
    desired_end: str = Field(..., min_length=1)