from app.breakers.circuit_breakers import cb_auth
from app.clients.base_client import _call_with_breaker
from app.config import AUTH_SERVICE_URL

async def register_user(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/register", data, request_id, None)

async def login_user(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/login", data, request_id, None)

async def google_login_user(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/auth/google", data, request_id, None)

async def refresh_user_token(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/refresh", data, request_id, None)

async def logout_user(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/logout", data, request_id, None)

async def forgot_password(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/password/forgot", data, request_id, None)

async def reset_password(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/password/reset", data, request_id, None)

async def request_email_verification(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/email/verify/request", data, request_id, None)

async def confirm_email_verification(data: dict, request_id: str | None = None):
    return await _call_with_breaker(cb_auth, "POST", f"{AUTH_SERVICE_URL}/email/verify/confirm", data, request_id, None)

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