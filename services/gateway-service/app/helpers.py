import time
import asyncio
import httpx
from fastapi import HTTPException
from typing import List, Dict, Any

from .clients import (
    cb_auth,
    cb_user,
    cb_handyman,
    cb_availability,
    cb_match,
    cb_booking,
    cb_notification,
    get_auth_user_by_email,
    get_booking,
)
from .config import SERVICE_BASE_URLS


def _breaker_registry():
    return {
        "auth-service": cb_auth,
        "user-service": cb_user,
        "handyman-service": cb_handyman,
        "availability-service": cb_availability,
        "match-service": cb_match,
        "booking-service": cb_booking,
        "notification-service": cb_notification,
    }


def _service_urls(path: str) -> Dict[str, str]:
    bases = SERVICE_BASE_URLS()
    return {name: f"{base}{path}" for name, base in bases.items()}


async def _fetch_json(
    *,
    client: httpx.AsyncClient,
    name: str,
    url: str,
    request_id: str,
) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        r = await client.get(url, headers={"X-Request-Id": request_id})
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        try:
            data: Any = r.json()
        except Exception:
            data = {"raw": (r.text or "")[:500]}

        return {
            "service": name,
            "url": url,
            "status": "up" if r.status_code == 200 else "down",
            "http_status": r.status_code,
            "latency_ms": latency_ms,
            "data": data,
        }
    except Exception as e:
        return {
            "service": name,
            "url": url,
            "status": "down",
            "error": str(e),
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "data": None,
        }


def _overall_status(results: List[Dict[str, Any]]) -> str:
    return "up" if all(r.get("status") == "up" for r in results) else "degraded"


def _user_email(payload: dict) -> str:
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return str(email)


def _has_role(payload: dict, role: str) -> bool:
    roles = payload.get("roles") or []
    return role.lower() in {str(r).lower() for r in roles}


def _auth_user_has_any_role(auth_user: dict, allowed_roles: list[str]) -> bool:
    roles = {str(r).lower() for r in (auth_user.get("roles") or [])}
    allowed = {str(r).lower() for r in allowed_roles}
    return not roles.isdisjoint(allowed)


async def _get_auth_user_after_register(email: str, request_id: str) -> dict:
    try:
        return await get_auth_user_by_email(email, request_id=request_id, user_payload=None)
    except HTTPException as e:
        raise HTTPException(
            status_code=502,
            detail=f"Auth user was registered but could not be fetched afterwards. status={e.status_code}"
        )


async def _booking_owned_or_admin(booking_id: str, payload: dict, request_id: str) -> dict:
    booking = await get_booking(booking_id, request_id=request_id, user_payload=payload)

    if _has_role(payload, "admin"):
        return booking

    current_email = _user_email(payload)
    is_user_owner = booking.get("user_email") == current_email
    is_handyman_owner = booking.get("handyman_email") == current_email

    if is_user_owner or is_handyman_owner:
        return booking

    raise HTTPException(status_code=403, detail="Forbidden for this booking")
