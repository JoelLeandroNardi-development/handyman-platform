from __future__ import annotations

from fastapi import Query

from ..helpers import avail_key
from ...infrastructure.cache import redis_client
from ...infrastructure.repository import get_reservation, delete_reservation

class AvailabilityQueryService:
    async def get_availability(email: str) -> dict:
        key = avail_key(email)
        slots = await redis_client.lrange(key, 0, -1)

        parsed: list[dict] = []
        for slot in slots:
            try:
                start, end = slot.split("|")
                parsed.append({"start": start, "end": end})
            except Exception:
                continue

        return {"email": email, "slots": parsed}

    async def list_all_availability(
        limit: int = Query(200, ge=1, le=1000),
        cursor: int = Query(0, ge=0),
    ) -> dict:
        pattern = "availability:*"
        next_cursor, keys = await redis_client.scan(cursor=cursor, match=pattern, count=limit)

        items: list[dict] = []
        for k in keys or []:
            if not isinstance(k, str) or ":" not in k:
                continue
            _, email = k.split(":", 1)
            slots = await redis_client.lrange(k, 0, -1)
            parsed: list[dict] = []
            for slot in slots or []:
                try:
                    start, end = slot.split("|")
                    parsed.append({"start": start, "end": end})
                except Exception:
                    continue
            items.append({"email": email, "slots": parsed})

        return {"cursor": int(next_cursor or 0), "items": items}

    async def get_reservation(booking_id: str) -> dict:
        res = await get_reservation(booking_id)
        return {"booking_id": booking_id, "reservation": res}