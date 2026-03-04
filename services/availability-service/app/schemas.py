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