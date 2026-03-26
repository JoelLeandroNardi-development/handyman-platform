from app.breakers.circuit_breakers import cb_availability
from app.clients.base_client import _call_with_breaker
from app.config import AVAILABILITY_SERVICE_URL

async def set_availability(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "POST", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", data, request_id, user_payload)

async def get_availability(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "GET", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", None, request_id, user_payload)

async def clear_availability(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_availability, "DELETE", f"{AVAILABILITY_SERVICE_URL}/availability/{email}", None, request_id, user_payload)

async def list_all_availability(request_id: str | None = None, user_payload: dict | None = None, limit: int = 200, cursor: int = 0):
    return await _call_with_breaker(cb_availability, "GET", f"{AVAILABILITY_SERVICE_URL}/availability?limit={limit}&cursor={cursor}", None, request_id, user_payload)