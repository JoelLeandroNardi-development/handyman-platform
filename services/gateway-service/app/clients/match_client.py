from app.breakers.circuit_breakers import cb_match
from app.clients.base_client import _call_with_breaker
from app.config import MATCH_SERVICE_URL

async def match_request(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_match, "POST", f"{MATCH_SERVICE_URL}/match", data, request_id, user_payload)

async def list_match_logs(request_id: str | None = None, user_payload: dict | None = None, limit: int = 50, offset: int = 0, skill: str | None = None):
    qs = f"limit={limit}&offset={offset}"
    if skill:
        qs += f"&skill={skill}"
    return await _call_with_breaker(cb_match, "GET", f"{MATCH_SERVICE_URL}/match-logs?{qs}", None, request_id, user_payload)

async def delete_match_log(log_id: int, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(cb_match, "DELETE", f"{MATCH_SERVICE_URL}/match-logs/{log_id}", None, request_id, user_payload)