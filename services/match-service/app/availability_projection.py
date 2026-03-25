from __future__ import annotations

import json
from datetime import datetime

from shared.shared.intervals import overlaps

from .scoring import _as_utc, parse_dt
from .projections import redis_client

PROJ_AVAIL_KEY = "proj:availability:{email}"
PROJ_AVAIL_INDEX = "proj:availability:index"


def _clean_slots(slots: list[dict] | None) -> list[dict]:
    clean: list[dict] = []
    for s in (slots or []):
        if not isinstance(s, dict):
            continue
        start = s.get("start")
        end = s.get("end")
        if not start or not end:
            continue
        try:
            sdt = parse_dt(start)
            edt = parse_dt(end)
        except Exception:
            continue
        if edt <= sdt:
            continue
        clean.append({"start": sdt.isoformat(), "end": edt.isoformat()})
    return clean


async def get_availability_slots(email: str) -> list[dict] | None:
    if not email:
        return None
    raw = await redis_client.get(PROJ_AVAIL_KEY.format(email=email))
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj.get("slots") or []
    except Exception:
        return None


async def delete_availability_projection(email: str) -> None:
    if not email:
        return
    pipe = redis_client.pipeline()
    pipe.delete(PROJ_AVAIL_KEY.format(email=email))
    pipe.srem(PROJ_AVAIL_INDEX, email)
    await pipe.execute()


def projected_has_overlap(slots: list[dict], desired_start: datetime, desired_end: datetime) -> bool:
    ds = _as_utc(desired_start)
    de = _as_utc(desired_end)

    if de <= ds:
        return False

    for slot in slots or []:
        try:
            ss = parse_dt(slot.get("start"))
            ee = parse_dt(slot.get("end"))
        except Exception:
            continue

        if overlaps(ss, ee, ds, de):
            return True

    return False


async def availability_projection_count() -> int:
    try:
        return int(await redis_client.scard(PROJ_AVAIL_INDEX))
    except Exception:
        return 0
