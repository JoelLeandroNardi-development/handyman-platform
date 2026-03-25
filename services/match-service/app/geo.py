"""Geo module – haversine distance, bucket grid helpers, and radius utilities for /match."""
from __future__ import annotations

import math
import os
from datetime import datetime

from .scoring import _as_utc

GRID_DEG = float(os.getenv("MATCH_GRID_DEG") or "0.05")
TIME_BUCKET_SECONDS = int(os.getenv("MATCH_TIME_BUCKET_SECONDS") or "900")


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres between two (lat, lon) points."""
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def bucket_id(lat: float, lon: float) -> tuple[int, int]:
    """Map (lat, lon) to a grid bucket using GRID_DEG resolution."""
    return int(math.floor(lat / GRID_DEG)), int(math.floor(lon / GRID_DEG))


def time_bucket(desired_start: datetime) -> int:
    """Map a datetime to a coarse time bucket for cache key construction."""
    epoch = int(_as_utc(desired_start).timestamp())
    return epoch // TIME_BUCKET_SECONDS


def km_to_deg_lat(km: float) -> float:
    return km / 111.0


def km_to_deg_lon(km: float, lat: float) -> float:
    c = math.cos(math.radians(lat))
    if abs(c) < 0.01:
        c = 0.01
    return km / (111.0 * c)


def buckets_in_radius(lat: float, lon: float, radius_km: float) -> list[tuple[int, int]]:
    """Return all grid bucket IDs within radius_km of (lat, lon)."""
    d_lat = km_to_deg_lat(radius_km)
    d_lon = km_to_deg_lon(radius_km, lat)

    lat_min = lat - d_lat
    lat_max = lat + d_lat
    lon_min = lon - d_lon
    lon_max = lon + d_lon

    b_lat_min = int(math.floor(lat_min / GRID_DEG))
    b_lat_max = int(math.floor(lat_max / GRID_DEG))
    b_lon_min = int(math.floor(lon_min / GRID_DEG))
    b_lon_max = int(math.floor(lon_max / GRID_DEG))

    out = []
    for bl in range(b_lat_min, b_lat_max + 1):
        for bo in range(b_lon_min, b_lon_max + 1):
            out.append((bl, bo))
    return out
