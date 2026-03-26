import json
import httpx
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from ..breakers.breaker import CircuitBreaker, CircuitBreakerOpen


DEFAULT_TIMEOUT = 3.0


def _base_headers(request_id: str | None, user_payload: dict | None):
    headers: dict[str, str] = {}
    if request_id:
        headers["X-Request-Id"] = request_id
    if user_payload:
        sub = user_payload.get("sub")
        roles = user_payload.get("roles")
        if sub:
            headers["X-User-Sub"] = str(sub)
            headers["X-User-Email"] = str(sub)
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