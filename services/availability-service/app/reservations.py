import json
import time
from datetime import datetime
from dateutil import parser

from .redis_client import redis_client

RES_TTL_SECONDS = 300  # 5 minutes
EXPIRY_ZSET = "reservation_expiry"

def _res_key(booking_id: str) -> str:
    return f"reservation:{booking_id}"

def _res_handyman_set(email: str) -> str:
    return f"reservations_by_handyman:{email}"

def _parse(dt_str: str) -> datetime:
    return parser.isoparse(dt_str)

def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and a_end > b_start

async def create_reservation(
    booking_id: str,
    handyman_email: str,
    desired_start: str,
    desired_end: str,
) -> bool:
    """
    Idempotent reservation creation.
    Returns True if reservation stored, False if conflicts with existing reservations.
    """
    ds = _parse(desired_start)
    de = _parse(desired_end)

    # check conflicts vs existing reservations for this handyman
    set_key = _res_handyman_set(handyman_email)
    existing = await redis_client.smembers(set_key)
    for bid in existing:
        data = await redis_client.get(_res_key(bid))
        if not data:
            continue
        try:
            obj = json.loads(data)
            ods = _parse(obj["desired_start"])
            ode = _parse(obj["desired_end"])
        except Exception:
            continue
        if overlaps(ods, ode, ds, de):
            return False

    # store reservation
    payload = {
        "booking_id": booking_id,
        "handyman_email": handyman_email,
        "desired_start": desired_start,
        "desired_end": desired_end,
        "created_at": time.time(),
    }

    pipe = redis_client.pipeline()
    pipe.set(_res_key(booking_id), json.dumps(payload), ex=RES_TTL_SECONDS)
    pipe.sadd(set_key, booking_id)
    pipe.expire(set_key, RES_TTL_SECONDS + 30)
    pipe.zadd(EXPIRY_ZSET, {booking_id: time.time() + RES_TTL_SECONDS})
    await pipe.execute()
    return True

async def get_reservation(booking_id: str) -> dict | None:
    raw = await redis_client.get(_res_key(booking_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

async def delete_reservation(booking_id: str):
    res = await get_reservation(booking_id)
    pipe = redis_client.pipeline()
    pipe.delete(_res_key(booking_id))
    pipe.zrem(EXPIRY_ZSET, booking_id)
    if res and res.get("handyman_email"):
        pipe.srem(_res_handyman_set(res["handyman_email"]), booking_id)
    await pipe.execute()