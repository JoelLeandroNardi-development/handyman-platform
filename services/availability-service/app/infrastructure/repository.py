from __future__ import annotations

import json
import time

from .config import RESERVATION_TTL_SECONDS
from ..domain.constants import DataKey, EXPIRY_ZSET
from .cache import redis_client
from ..application.helpers import res_key, res_handyman_set, parse
from shared.core.utils.intervals import overlaps

RES_TTL_SECONDS = RESERVATION_TTL_SECONDS

async def create_reservation(
    booking_id: str,
    user_email: str,
    handyman_email: str,
    desired_start: str,
    desired_end: str,
) -> bool:
    ds = parse(desired_start)
    de = parse(desired_end)

    set_key = res_handyman_set(handyman_email)
    existing = await redis_client.smembers(set_key)
    for bid in existing:
        data = await redis_client.get(res_key(bid))
        if not data:
            continue
        try:
            obj = json.loads(data)
            ods = parse(obj[DataKey.DESIRED_START])
            ode = parse(obj[DataKey.DESIRED_END])
        except Exception:
            continue
        if overlaps(ods, ode, ds, de):
            return False

    payload = {
        DataKey.BOOKING_ID: booking_id,
        DataKey.USER_EMAIL: user_email,
        DataKey.HANDYMAN_EMAIL: handyman_email,
        DataKey.DESIRED_START: desired_start,
        DataKey.DESIRED_END: desired_end,
        DataKey.CREATED_AT: time.time(),
    }

    pipe = redis_client.pipeline()
    pipe.set(res_key(booking_id), json.dumps(payload), ex=RESERVATION_TTL_SECONDS)
    pipe.sadd(set_key, booking_id)
    pipe.expire(set_key, RESERVATION_TTL_SECONDS + 30)
    pipe.zadd(EXPIRY_ZSET, {booking_id: time.time() + RESERVATION_TTL_SECONDS})
    await pipe.execute()
    return True

async def get_reservation(booking_id: str) -> dict | None:
    raw = await redis_client.get(res_key(booking_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

async def delete_reservation(booking_id: str) -> None:
    res = await get_reservation(booking_id)
    pipe = redis_client.pipeline()
    pipe.delete(res_key(booking_id))
    pipe.zrem(EXPIRY_ZSET, booking_id)
    if res and res.get(DataKey.HANDYMAN_EMAIL):
        pipe.srem(res_handyman_set(res[DataKey.HANDYMAN_EMAIL]), booking_id)
    await pipe.execute()