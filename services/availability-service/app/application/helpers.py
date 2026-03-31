from __future__ import annotations
import datetime

from dateutil import parser

from ..domain.events import build_event
from ..domain.schemas import AvailabilitySlot
from ..infrastructure.outbox_worker import enqueue_domain_event

def res_key(booking_id: str) -> str:
    return f"reservation:{booking_id}"

def res_handyman_set(email: str) -> str:
    return f"reservations_by_handyman:{email}"

def parse(dt_str: str) -> datetime:
    return parser.isoparse(dt_str)

def slots_payload(slots: list[AvailabilitySlot]) -> list[dict]:
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

def avail_key(email: str) -> str:
    return f"availability:{email}"

def parse_raw_slot(raw: str):
    try:
        s, e = raw.split("|")
        return parser.isoparse(s), parser.isoparse(e)
    except Exception:
        return None