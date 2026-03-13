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
    headers: dict[str, str] = {}
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


def _safe_json(resp: httpx.Response) -> dict:
    if not resp.content:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


async def _call_with_breaker(
    breaker: CircuitBreaker,
    method: str,
    url: str,
    payload: dict | None,
    request_id: str | None,
    user_payload: dict | None,
):
    try:
        await breaker.allow_request()
    except CircuitBreakerOpen as e:
        raise HTTPException(status_code=503, detail=str(e))

    headers = _base_headers(request_id, user_payload)
    safe_payload = jsonable_encoder(payload) if payload is not None else None

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.request(method=method, url=url, json=safe_payload, headers=headers)

        if 200 <= resp.status_code < 300:
            await breaker.record_success()
            return _safe_json(resp)

        await breaker.record_failure()

        detail = _safe_json(resp)
        raise HTTPException(status_code=resp.status_code, detail=detail)

    except httpx.TimeoutException:
        await breaker.record_failure()
        raise HTTPException(status_code=504, detail=f"Timeout calling upstream: {url}")
    except HTTPException:
        raise
    except Exception as e:
        await breaker.record_failure()
        raise HTTPException(status_code=502, detail=f"Bad gateway calling upstream: {url}. err={type(e).__name__}: {e}")


async def register_user(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/register", data, request_id, None)


async def login_user(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/login", data, request_id, None)


async def list_auth_users(request_id: str | None = None, user_payload: dict | None = None, limit: int = 50, offset: int = 0):
    return await _call_with_breaker(cb_auth, "GET", f"{AUTH_SERVICE_URL}/auth-users?limit={limit}&offset={offset}", None, request_id, user_payload)


async def get_auth_user(user_id: int, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_auth, "GET", f"{AUTH_SERVICE_URL}/auth-users/{user_id}", None, request_id, user_payload)


async def get_auth_user_by_email(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_auth, "GET", f"{AUTH_SERVICE_URL}/auth-users/by-email/{email}", None, request_id, user_payload)


async def update_auth_user(user_id: int, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_auth, "PUT", f"{AUTH_SERVICE_URL}/auth-users/{user_id}", data, request_id, user_payload)


async def delete_auth_user(user_id: int, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_auth, "DELETE", f"{AUTH_SERVICE_URL}/auth-users/{user_id}", None, request_id, user_payload)


async def create_user(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_user, "POST", f"{USER_SERVICE_URL}/users", data, request_id, user_payload)


async def update_user_location(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_user, "PUT", f"{USER_SERVICE_URL}/users/{email}/location", data, request_id, user_payload)


async def update_user(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_user, "PUT", f"{USER_SERVICE_URL}/users/{email}", data, request_id, user_payload)


async def delete_user(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_user, "DELETE", f"{USER_SERVICE_URL}/users/{email}", None, request_id, user_payload)


async def list_users(request_id: str | None = None, user_payload: dict | None = None, limit: int = 50, offset: int = 0):
    return await _call_with_breaker(cb_user, "GET", f"{USER_SERVICE_URL}/users?limit={limit}&offset={offset}", None, request_id, user_payload)


async def get_user(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_user, "GET", f"{USER_SERVICE_URL}/users/{email}", None, request_id, user_payload)


async def create_handyman(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "POST", f"{HANDYMAN_SERVICE_URL}/handymen", data, request_id, user_payload)


async def update_handyman_location(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "PUT", f"{HANDYMAN_SERVICE_URL}/handymen/{email}/location", data, request_id, user_payload)


async def update_handyman(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "PUT", f"{HANDYMAN_SERVICE_URL}/handymen/{email}", data, request_id, user_payload)


async def delete_handyman(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "DELETE", f"{HANDYMAN_SERVICE_URL}/handymen/{email}", None, request_id, user_payload)


async def get_handyman(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_handyman, "GET", f"{HANDYMAN_SERVICE_URL}/handymen/{email}", None, request_id, user_payload)


async def list_handymen(request_id: str | None = None, user_payload: dict | None = None, limit: int = 200, offset: int = 0):
    return await _call_with_breaker(cb_handyman, "GET", f"{HANDYMAN_SERVICE_URL}/handymen?limit={limit}&offset={offset}", None, request_id, user_payload)


async def update_handyman_location_and_fetch(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    await update_handyman_location(email, data, request_id, user_payload)
    return await get_handyman(email, request_id, user_payload)


async def get_skills_catalog(
    request_id: str | None = None,
    user_payload: dict | None = None,
    active_only: bool = True,
):
    active_q = "true" if active_only else "false"
    return await _call_with_breaker(
        cb_handyman,
        "GET",
        f"{HANDYMAN_SERVICE_URL}/skills-catalog?active_only={active_q}",
        None,
        request_id,
        user_payload,
    )


async def get_skills_catalog_flat(
    request_id: str | None = None,
    user_payload: dict | None = None,
    active_only: bool = True,
):
    active_q = "true" if active_only else "false"
    return await _call_with_breaker(
        cb_handyman,
        "GET",
        f"{HANDYMAN_SERVICE_URL}/skills-catalog/flat?active_only={active_q}",
        None,
        request_id,
        user_payload,
    )


async def replace_skills_catalog(
    data: dict,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await _call_with_breaker(
        cb_handyman,
        "PUT",
        f"{HANDYMAN_SERVICE_URL}/admin/skills-catalog",
        data,
        request_id,
        user_payload,
    )


async def patch_skills_catalog(
    data: dict,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await _call_with_breaker(
        cb_handyman,
        "PATCH",
        f"{HANDYMAN_SERVICE_URL}/admin/skills-catalog",
        data,
        request_id,
        user_payload,
    )


async def get_handymen_with_invalid_skills(
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await _call_with_breaker(
        cb_handyman,
        "GET",
        f"{HANDYMAN_SERVICE_URL}/admin/handymen/invalid-skills",
        None,
        request_id,
        user_payload,
    )


async def create_handyman_review(
    data: dict,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await _call_with_breaker(
        cb_handyman,
        "POST",
        f"{HANDYMAN_SERVICE_URL}/handymen/reviews",
        data,
        request_id,
        user_payload,
    )


async def list_handyman_reviews(
    email: str,
    request_id: str | None = None,
    user_payload: dict | None = None,
    limit: int = 50,
    offset: int = 0,
):
    return await _call_with_breaker(
        cb_handyman,
        "GET",
        f"{HANDYMAN_SERVICE_URL}/handymen/{email}/reviews?limit={limit}&offset={offset}",
        None,
        request_id,
        user_payload,
    )


async def set_availability(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "POST", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", data, request_id, user_payload)


async def get_availability(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "GET", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", None, request_id, user_payload)


async def clear_availability(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "DELETE", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", None, request_id, user_payload)


async def list_all_availability(request_id: str | None = None, user_payload: dict | None = None, limit: int = 200, cursor: int = 0):
    return await _call_with_breaker(cb_availability, "GET", f"{AVAILABILITY_SERVICE_URL}/availability?limit={limit}&cursor={cursor}", None, request_id, user_payload)


async def match_request(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_match, "POST", f"{MATCH_SERVICE_URL}/match", data, request_id, user_payload)


async def list_match_logs(request_id: str | None = None, user_payload: dict | None = None, limit: int = 50, offset: int = 0, skill: str | None = None):
    qs = f"limit={limit}&offset={offset}"
    if skill:
        qs += f"&skill={skill}"
    return await _call_with_breaker(cb_match, "GET", f"{MATCH_SERVICE_URL}/match-logs?{qs}", None, request_id, user_payload)


async def delete_match_log(log_id: int, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_match, "DELETE", f"{MATCH_SERVICE_URL}/match-logs/{log_id}", None, request_id, user_payload)


async def create_booking(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "POST", f"{BOOKING_SERVICE_URL}/bookings", data, request_id, user_payload)


async def get_booking(booking_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "GET", f"{BOOKING_SERVICE_URL}/bookings/{booking_id}", None, request_id, user_payload)


async def confirm_booking(booking_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "POST", f"{BOOKING_SERVICE_URL}/bookings/{booking_id}/confirm", None, request_id, user_payload)


async def cancel_booking(booking_id: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "POST", f"{BOOKING_SERVICE_URL}/bookings/{booking_id}/cancel", data, request_id, user_payload)


async def complete_booking_as_user(booking_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(
        cb_booking,
        "POST",
        f"{BOOKING_SERVICE_URL}/bookings/{booking_id}/complete/user",
        None,
        request_id,
        user_payload,
    )


async def complete_booking_as_handyman(booking_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(
        cb_booking,
        "POST",
        f"{BOOKING_SERVICE_URL}/bookings/{booking_id}/complete/handyman",
        None,
        request_id,
        user_payload,
    )


async def reject_booking(booking_id: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(
        cb_booking,
        "POST",
        f"{BOOKING_SERVICE_URL}/bookings/{booking_id}/reject",
        data,
        request_id,
        user_payload,
    )


async def list_bookings(request_id: str | None = None, user_payload: dict | None = None, limit: int = 50, offset: int = 0, status: str | None = None, user_email: str | None = None, handyman_email: str | None = None):
    qs = f"limit={limit}&offset={offset}"
    if status:
        qs += f"&status={status}"
    if user_email:
        qs += f"&user_email={user_email}"
    if handyman_email:
        qs += f"&handyman_email={handyman_email}"
    return await _call_with_breaker(cb_booking, "GET", f"{BOOKING_SERVICE_URL}/bookings?{qs}", None, request_id, user_payload)


async def admin_update_booking(booking_id: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "PUT", f"{BOOKING_SERVICE_URL}/bookings/{booking_id}", data, request_id, user_payload)


async def admin_delete_booking(booking_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "DELETE", f"{BOOKING_SERVICE_URL}/bookings/{booking_id}", None, request_id, user_payload)