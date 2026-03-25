"""Clients module – HTTP client calls to handyman-service, availability-service, and booking-service."""
from __future__ import annotations

import os

import httpx

from .projections import _normalize_handyman
from .availability_projection import _clean_slots

HANDYMAN_SERVICE_URL = os.getenv("HANDYMAN_SERVICE_URL", "http://handyman-service:8000")
AVAILABILITY_SERVICE_URL = os.getenv("AVAILABILITY_SERVICE_URL", "http://availability-service:8000")
BOOKING_SERVICE_URL = os.getenv("BOOKING_SERVICE_URL", "http://booking-service:8000")

HTTP_TIMEOUT = 2.0


async def fetch_handymen_http() -> list[dict]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        r = await client.get(f"{HANDYMAN_SERVICE_URL}/handymen")
        r.raise_for_status()
        data = r.json()

    out: list[dict] = []
    for h in data or []:
        if not isinstance(h, dict):
            continue
        normalized = _normalize_handyman(h)
        if normalized.get("email"):
            out.append(normalized)
    return out


async def fetch_availability_http(email: str) -> list[dict] | None:
    if not email:
        return None

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.get(f"{AVAILABILITY_SERVICE_URL}/availability/{email}")
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None

    slots = data.get("slots") or []
    return _clean_slots(slots)


async def fetch_completed_jobs_counts_batch(emails: list[str]) -> dict[str, int]:
    unique_emails = list(dict.fromkeys([str(e).strip() for e in (emails or []) if str(e).strip()]))
    if not unique_emails:
        return {}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.post(
                f"{BOOKING_SERVICE_URL}/bookings/completed-counts",
                json=unique_emails,
            )
            r.raise_for_status()
            data = r.json() or {}
    except Exception:
        return {}

    raw_counts = data.get("counts") if isinstance(data, dict) else {}
    if not isinstance(raw_counts, dict):
        return {}

    out: dict[str, int] = {}
    for email, value in raw_counts.items():
        if not isinstance(email, str):
            continue
        try:
            out[email] = int(value or 0)
        except Exception:
            continue
    return out
