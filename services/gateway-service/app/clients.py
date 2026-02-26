import json
import httpx
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from .config import (
    AUTH_SERVICE_URL,
    USER_SERVICE_URL,
    HANDYMAN_SERVICE_URL,
    AVAILABILITY_SERVICE_URL,
    MATCH_SERVICE_URL,
    BOOKING_SERVICE_URL,
)
from .breaker import CircuitBreaker, CircuitBreakerOpen

DEFAULT_TIMEOUT = 3.0

cb_auth = CircuitBreaker("auth-service", 5, 10)
cb_user = CircuitBreaker("user-service", 5, 10)
cb_handyman = CircuitBreaker("handyman-service", 5, 10)
cb_availability = CircuitBreaker("availability-service", 5, 10)
cb_match = CircuitBreaker("match-service", 5, 10)
cb_booking = CircuitBreaker("booking-service", 5, 10)

def _base_headers(request_id: str | None, user_payload: dict | None):
    headers = {}
    if request_id:
        headers["X-Request-Id"] = request_id
    if user_payload:
        sub = user_payload.get("sub")
        roles = user_payload.get("roles")
        if sub:
            headers["X-User-Sub"] = str(sub)
        if roles is not None:
            headers["X-User-Roles"] = json.dumps(roles)
    return headers

async def _call_with_breaker(breaker: CircuitBreaker, method: str, url: str, payload: dict | None, request_id: str | None, user_payload: dict | None):
    try:
        await breaker.allow_request()
    except CircuitBreakerOpen as e:
        raise HTTPException(status_code=503, detail=str(e))

    headers = _base_headers(request_id, user_payload)
    safe_payload = jsonable_encoder(payload) if payload is not None else None

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.request(method=method, url=url, json=safe_payload, headers=headers)
            resp.raise_for_status()
            await breaker.record_success()
            return resp.json() if resp.content else {}
    except httpx.TimeoutException:
        await breaker.record_failure()
        raise HTTPException(status_code=504, detail=f"Timeout calling upstream: {url}")
    except httpx.HTTPStatusError as e:
        await breaker.record_failure()
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception:
        await breaker.record_failure()
        raise HTTPException(status_code=502, detail=f"Bad gateway calling upstream: {url}")

async def register_user(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/register", data, request_id, None)

async def login_user(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/login", data, request_id, None)

async def create_user(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_user, "POST", f"{USER_SERVICE_URL}/users", data, request_id, user_payload)

async def update_user_location(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_user, "PUT", f"{USER_SERVICE_URL}/users/{email}/location", data, request_id, user_payload)

async def get_user(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_user, "GET", f"{USER_SERVICE_URL}/users/{email}", None, request_id, user_payload)

async def create_handyman(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "POST", f"{HANDYMAN_SERVICE_URL}/handymen", data, request_id, user_payload)

async def update_handyman_location(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "PUT", f"{HANDYMAN_SERVICE_URL}/handymen/{email}/location", data, request_id, user_payload)

async def get_handyman(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "GET", f"{HANDYMAN_SERVICE_URL}/handymen/{email}", None, request_id, user_payload)

async def list_handymen(request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "GET", f"{HANDYMAN_SERVICE_URL}/handymen", None, request_id, user_payload)

async def update_handyman_location_and_fetch(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    await update_handyman_location(email, data, request_id, user_payload)
    return await get_handyman(email, request_id, user_payload)

async def set_availability(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "POST", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", data, request_id, user_payload)

async def get_availability(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "GET", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", None, request_id, user_payload)

async def clear_availability(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "DELETE", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", None, request_id, user_payload)

async def match_request(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_match, "POST", f"{MATCH_SERVICE_URL}/match", data, request_id, user_payload)

# ---- Booking ----

async def create_booking(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "POST", f"{BOOKING_SERVICE_URL}/bookings", data, request_id, user_payload)

async def get_booking(booking_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "GET", f"{BOOKING_SERVICE_URL}/bookings/{booking_id}", None, request_id, user_payload)

async def confirm_booking(booking_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "POST", f"{BOOKING_SERVICE_URL}/bookings/{booking_id}/confirm", None, request_id, user_payload)