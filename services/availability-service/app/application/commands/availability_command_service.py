from __future__ import annotations

from fastapi import HTTPException
from dateutil import parser

from shared.shared.intervals import fully_contains as contains_interval

from ..helpers import slots_payload, avail_key, emit_availability_updated
from ...domain.schemas import SetAvailability, OverlapRequest
from ...infrastructure.cache import redis_client
from ...infrastructure.repository import delete_reservation

class AvailabilityCommandService:
    async def set_availability(email: str, data: SetAvailability):
        key = avail_key(email)
        await redis_client.delete(key)

        if data.slots:
            await redis_client.rpush(key, *[f"{slot.start}|{slot.end}" for slot in data.slots])

        await emit_availability_updated(email, slots_payload(data.slots))
        return {"message": "Availability updated"}

    async def clear_availability(email: str):
        key = avail_key(email)
        await redis_client.delete(key)
        await emit_availability_updated(email, [])
        return {"message": "Availability cleared"}

    async def check_overlap(email: str, req: OverlapRequest):
        try:
            ds = parser.isoparse(req.desired_start)
            de = parser.isoparse(req.desired_end)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid datetime format")

        if de <= ds:
            return {"available": False}

        key = avail_key(email)
        slots = await redis_client.lrange(key, 0, -1)

        for slot in slots:
            try:
                s, e = slot.split("|")
                ss = parser.isoparse(s)
                ee = parser.isoparse(e)
            except Exception:
                continue

            if contains_interval(ss, ee, ds, de):
                return {"available": True}

        return {"available": False}

    async def delete_reservation(booking_id: str):
        await delete_reservation(booking_id)
        return {"message": "deleted", "booking_id": booking_id}