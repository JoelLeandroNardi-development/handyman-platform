from __future__ import annotations

from fastapi import APIRouter, HTTPException
from dateutil import parser

from .redis_client import redis_client
from .schemas import SetAvailability, OverlapRequest, AvailabilitySlot
from .reservations import overlaps
from .events import build_event
from .outbox_worker import enqueue_domain_event

router = APIRouter()


def redis_key(email: str) -> str:
    return f"availability:{email}"


def _slots_payload(slots: list[AvailabilitySlot]) -> list[dict]:
    """
    Convert SetAvailability.slots into a JSON-friendly payload.
    Slots are strings, but keep it explicit and defensive.
    """
    out: list[dict] = []
    for s in slots or []:
        try:
            out.append({"start": str(s.start), "end": str(s.end)})
        except Exception:
            continue
    return out


async def emit_availability_updated(email: str, slots_payload: list[dict]) -> None:
    # IMPORTANT (Approach A): include full slots so Match can project without HTTP calls.
    ev = build_event("availability.updated", {"email": email, "slots": slots_payload})
    await enqueue_domain_event(ev)


@router.post("/availability/{email}")
async def set_availability(email: str, data: SetAvailability):
    key = redis_key(email)
    await redis_client.delete(key)

    # store as start|end
    if data.slots:
        await redis_client.rpush(key, *[f"{slot.start}|{slot.end}" for slot in data.slots])

    await emit_availability_updated(email, _slots_payload(data.slots))
    return {"message": "Availability updated"}


@router.get("/availability/{email}")
async def get_availability(email: str):
    key = redis_key(email)
    slots = await redis_client.lrange(key, 0, -1)

    parsed: list[dict] = []
    for slot in slots:
        try:
            start, end = slot.split("|")
            parsed.append({"start": start, "end": end})
        except Exception:
            continue

    return {"email": email, "slots": parsed}


@router.delete("/availability/{email}")
async def clear_availability(email: str):
    key = redis_key(email)
    await redis_client.delete(key)

    # slots are now empty
    await emit_availability_updated(email, [])
    return {"message": "Availability cleared"}


@router.post("/availability/{email}/overlap")
async def check_overlap(email: str, req: OverlapRequest):
    """
    Still useful for debugging and manual checks.
    Match should stop calling this in Approach A.
    """
    try:
        ds = parser.isoparse(req.desired_start)
        de = parser.isoparse(req.desired_end)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    if de <= ds:
        return {"available": False}

    key = redis_key(email)
    slots = await redis_client.lrange(key, 0, -1)

    for slot in slots:
        try:
            s, e = slot.split("|")
            ss = parser.isoparse(s)
            ee = parser.isoparse(e)
        except Exception:
            continue

        if overlaps(ss, ee, ds, de):
            return {"available": True}

    return {"available": False}