from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from dateutil import parser

from .redis_client import redis_client
from .schemas import SetAvailability, OverlapRequest, AvailabilitySlot
from .reservations import overlaps, get_reservation, delete_reservation
from .events import build_event
from .outbox_worker import enqueue_domain_event

router = APIRouter()


def redis_key(email: str) -> str:
    return f"availability:{email}"


def _slots_payload(slots: list[AvailabilitySlot]) -> list[dict]:
    out: list[dict] = []
    for s in slots or []:
        try:
            out.append({"start": str(s.start), "end": str(s.end)})
        except Exception:
            continue
    return out


async def emit_availability_updated(email: str, slots_payload: list[dict]) -> None:
    ev = build_event("availability.updated", {"email": email, "slots": slots_payload})
    await enqueue_domain_event(ev)


@router.post("/availability/{email}")
async def set_availability(email: str, data: SetAvailability):
    key = redis_key(email)
    await redis_client.delete(key)

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
    await emit_availability_updated(email, [])
    return {"message": "Availability cleared"}


@router.post("/availability/{email}/overlap")
async def check_overlap(email: str, req: OverlapRequest):
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


@router.get("/availability")
async def list_all_availability(
    limit: int = Query(200, ge=1, le=1000),
    cursor: int = Query(0, ge=0),
):
    """
    Lists availability keys via SCAN.
    Returns: {cursor, items:[{email, slots:[{start,end}]}]}
    """
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


@router.get("/reservations/{booking_id}")
async def get_reservation_endpoint(booking_id: str):
    res = await get_reservation(booking_id)
    return {"booking_id": booking_id, "reservation": res}


@router.delete("/reservations/{booking_id}")
async def delete_reservation_endpoint(booking_id: str):
    await delete_reservation(booking_id)
    return {"message": "deleted", "booking_id": booking_id}