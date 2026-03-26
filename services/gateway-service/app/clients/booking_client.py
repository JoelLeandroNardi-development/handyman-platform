from app.breakers.circuit_breakers import cb_booking
from app.clients.base_client import _call_with_breaker
from app.config import BOOKING_SERVICE_URL

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

async def get_completed_count(handyman_email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "GET", f"{BOOKING_SERVICE_URL}/bookings/completed-count/{handyman_email}", None, request_id, user_payload)

async def get_completed_counts_batch(emails: list[str], request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_booking, "POST", f"{BOOKING_SERVICE_URL}/bookings/completed-counts", emails, request_id, user_payload)