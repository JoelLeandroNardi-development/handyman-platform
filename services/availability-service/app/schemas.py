from pydantic import BaseModel
from typing import List


class AvailabilitySlot(BaseModel):
    start: str  # ISO datetime string
    end: str    # ISO datetime string


class SetAvailability(BaseModel):
    slots: List[AvailabilitySlot]
