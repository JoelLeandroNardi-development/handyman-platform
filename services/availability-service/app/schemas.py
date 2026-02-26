from pydantic import BaseModel
from typing import List

class AvailabilitySlot(BaseModel):
    start: str
    end: str

class SetAvailability(BaseModel):
    slots: List[AvailabilitySlot]

class OverlapRequest(BaseModel):
    desired_start: str
    desired_end: str