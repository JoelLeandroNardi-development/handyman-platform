import time
import uuid
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .redis_client import redis_client


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            print(
                f'{{"request_id":"{request_id}","method":"{request.method}","path":"{request.url.path}","status":500,"duration_ms":{duration_ms:.2f}}}'
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = request_id

        user_sub = getattr(request.state, "user_sub", None)
        user_roles = getattr(request.state, "user_roles", None)

        print(
            f'{{"request_id":"{request_id}","method":"{request.method}","path":"{request.url.path}","status":{response.status_code},"duration_ms":{duration_ms:.2f},"user_sub":"{user_sub}","user_roles":{user_roles}}}'
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_per_minute: int = 120):
        super().__init__(app)
        self.max_per_minute = max_per_minute

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/docs", "/openapi.json", "/health"):
            return await call_next(request)
        if request.url.path.startswith("/docs/"):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        user_sub = getattr(request.state, "user_sub", None)
        identity = f"user:{user_sub}" if user_sub else f"ip:{ip}"

        epoch_minute = int(time.time() // 60)
        key = f"rl:{identity}:{epoch_minute}"

        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 70)

        if count > self.max_per_minute:
            raise HTTPException(status_code=429, detail="Too many requests")

        return await call_next(request)
