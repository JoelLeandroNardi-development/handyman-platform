import time
from .redis_client import redis_client


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    """
    Redis-backed circuit breaker (shared across gateway instances).

    States:
      - CLOSED: allow traffic, count failures
      - OPEN: block traffic for reset_timeout seconds
      - HALF_OPEN: after timeout, allow a probe request
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout_seconds: int = 15,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds

    def _key_state(self):
        return f"cb:{self.name}:state"

    def _key_failures(self):
        return f"cb:{self.name}:failures"

    def _key_opened_at(self):
        return f"cb:{self.name}:opened_at"

    async def _get_state(self) -> str:
        state = await redis_client.get(self._key_state())
        return state or "CLOSED"

    async def allow_request(self) -> None:
        state = await self._get_state()

        if state == "CLOSED":
            return

        if state == "OPEN":
            opened_at = await redis_client.get(self._key_opened_at())
            if not opened_at:
                # safety: if no timestamp, close it
                await self.close()
                return

            opened_at = float(opened_at)
            now = time.time()

            if (now - opened_at) >= self.reset_timeout_seconds:
                # move to half-open and allow one probe
                await redis_client.set(self._key_state(), "HALF_OPEN")
                return

            raise CircuitBreakerOpen(f"Circuit breaker OPEN for {self.name}")

        # HALF_OPEN: allow one probe request
        if state == "HALF_OPEN":
            return

    async def record_success(self) -> None:
        # success closes breaker and resets failures
        await self.close()

    async def record_failure(self) -> None:
        state = await self._get_state()

        # If half-open fails, open immediately
        if state == "HALF_OPEN":
            await self.open()
            return

        # Otherwise count failures
        failures = await redis_client.incr(self._key_failures())
        if failures == 1:
            await redis_client.expire(self._key_failures(), 60)

        if failures >= self.failure_threshold:
            await self.open()

    async def open(self) -> None:
        now = str(time.time())
        pipe = redis_client.pipeline()
        pipe.set(self._key_state(), "OPEN")
        pipe.set(self._key_opened_at(), now)
        pipe.expire(self._key_state(), self.reset_timeout_seconds + 30)
        pipe.expire(self._key_opened_at(), self.reset_timeout_seconds + 30)
        await pipe.execute()

    async def close(self) -> None:
        pipe = redis_client.pipeline()
        pipe.set(self._key_state(), "CLOSED")
        pipe.delete(self._key_failures())
        pipe.delete(self._key_opened_at())
        pipe.expire(self._key_state(), 3600)
        await pipe.execute()
