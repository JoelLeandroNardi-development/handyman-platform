from __future__ import annotations

from datetime import datetime

from .geo import bucket_id, time_bucket


def cache_key(lat: float, lon: float, skill: str, degraded: bool, desired_start: datetime) -> str:
    mode = "degraded" if degraded else "strict"
    b_lat, b_lon = bucket_id(lat, lon)
    t = time_bucket(desired_start)
    return f"match:{mode}:{skill}:lat={b_lat}:lon={b_lon}:t={t}"


def bucket_set_key(mode: str, skill: str, b_lat: int, b_lon: int) -> str:
    return f"matchkeys:{mode}:{skill}:lat={b_lat}:lon={b_lon}"
