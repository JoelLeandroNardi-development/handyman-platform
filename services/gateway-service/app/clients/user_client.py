from .base_client import call_with_breaker
from ..breakers.circuit_breakers import cb_user
from ..config import USER_SERVICE_URL

async def create_user(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_user, "POST", f"{USER_SERVICE_URL}/users", data, request_id, user_payload)

async def update_user_location(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_user, "PUT", f"{USER_SERVICE_URL}/users/{email}/location", data, request_id, user_payload)

async def update_user(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_user, "PUT", f"{USER_SERVICE_URL}/users/{email}", data, request_id, user_payload)

async def delete_user(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_user, "DELETE", f"{USER_SERVICE_URL}/users/{email}", None, request_id, user_payload)

async def list_users(request_id: str | None = None, user_payload: dict | None = None, limit: int = 50, offset: int = 0):
    return await call_with_breaker(cb_user, "GET", f"{USER_SERVICE_URL}/users?limit={limit}&offset={offset}", None, request_id, user_payload)

async def get_user(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_user, "GET", f"{USER_SERVICE_URL}/users/{email}", None, request_id, user_payload)