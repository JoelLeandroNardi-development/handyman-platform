from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.service_loader import load_service_app_module

_PKG = "gateway_breaker_test_app"

class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, **_kw):
        self._store[key] = str(value)

    async def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)

    async def incr(self, key):
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    async def expire(self, key, ttl):
        pass

    async def mget(self, *keys):
        return [self._store.get(k) for k in keys]

    def pipeline(self):
        return FakePipeline(self)

class FakePipeline:
    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._ops: list = []

    def set(self, key, value, **_kw):
        self._ops.append(("set", key, value))

    def delete(self, *keys):
        for k in keys:
            self._ops.append(("delete", k))

    def expire(self, key, ttl):
        pass

    async def execute(self):
        results = []
        for op in self._ops:
            if op[0] == "set":
                self._redis._store[op[1]] = str(op[2])
                results.append(True)
            elif op[0] == "delete":
                self._redis._store.pop(op[1], None)
                results.append(True)
        self._ops.clear()
        return results

@pytest.fixture
def breaker_module(monkeypatch):
    fake_redis = FakeRedis()
    import types, sys

    injected_keys: list[str] = []

    for prefix in [_PKG, "app"]:
        clients_pkg = f"{prefix}.clients"
        redis_mod_name = f"{prefix}.clients.redis_client"

        if clients_pkg not in sys.modules:
            pkg = types.ModuleType(clients_pkg)
            pkg.__path__ = []
            sys.modules[clients_pkg] = pkg
            injected_keys.append(clients_pkg)

        redis_mod = types.ModuleType(redis_mod_name)
        redis_mod.redis_client = fake_redis
        sys.modules[redis_mod_name] = redis_mod
        injected_keys.append(redis_mod_name)

    mod = load_service_app_module(
        "gateway-service",
        "breakers/breaker",
        package_name=_PKG,
        reload_modules=True,
    )
    mod.redis_client = fake_redis
    yield mod, fake_redis

    breaker_full = f"{_PKG}.breakers.breaker"
    breaker_pkg = f"{_PKG}.breakers"
    for key in injected_keys + [breaker_full, breaker_pkg, _PKG]:
        sys.modules.pop(key, None)

@pytest.mark.unit
class TestCircuitBreakerClosed:
    @pytest.mark.asyncio
    async def test_starts_closed(self, breaker_module):
        mod, _ = breaker_module
        cb = mod.CircuitBreaker("test-svc", failure_threshold=3, reset_timeout_seconds=10)
        await cb.allow_request()

    @pytest.mark.asyncio
    async def test_success_keeps_closed(self, breaker_module):
        mod, _ = breaker_module
        cb = mod.CircuitBreaker("test-svc2", failure_threshold=3)
        await cb.record_success()
        await cb.allow_request()

@pytest.mark.unit
class TestCircuitBreakerTripping:
    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self, breaker_module):
        mod, _ = breaker_module
        cb = mod.CircuitBreaker("trip-svc", failure_threshold=3, reset_timeout_seconds=10)

        for _ in range(3):
            await cb.record_failure()

        with pytest.raises(mod.CircuitBreakerOpen):
            await cb.allow_request()

    @pytest.mark.asyncio
    async def test_below_threshold_stays_closed(self, breaker_module):
        mod, _ = breaker_module
        cb = mod.CircuitBreaker("under-svc", failure_threshold=5, reset_timeout_seconds=10)

        for _ in range(4):
            await cb.record_failure()

        await cb.allow_request()

@pytest.mark.unit
class TestCircuitBreakerHalfOpen:
    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self, breaker_module, monkeypatch):
        mod, fake_redis = breaker_module
        cb = mod.CircuitBreaker("half-svc", failure_threshold=2, reset_timeout_seconds=1)

        for _ in range(2):
            await cb.record_failure()

        opened_at_key = cb._key_opened_at()
        fake_redis._store[opened_at_key] = str(time.time() - 2)

        await cb.allow_request()

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self, breaker_module):
        mod, fake_redis = breaker_module
        cb = mod.CircuitBreaker("reopen-svc", failure_threshold=2, reset_timeout_seconds=10)

        # Force into HALF_OPEN
        fake_redis._store[cb._key_state()] = "HALF_OPEN"

        await cb.record_failure()

        with pytest.raises(mod.CircuitBreakerOpen):
            await cb.allow_request()

@pytest.mark.unit
class TestCircuitBreakerRecovery:
    @pytest.mark.asyncio
    async def test_success_in_half_open_closes(self, breaker_module):
        mod, fake_redis = breaker_module
        cb = mod.CircuitBreaker("recover-svc", failure_threshold=2, reset_timeout_seconds=10)

        fake_redis._store[cb._key_state()] = "HALF_OPEN"
        await cb.record_success()
        await cb.allow_request()

@pytest.mark.unit
class TestCircuitBreakerStatus:
    @pytest.mark.asyncio
    async def test_status_returns_dict(self, breaker_module):
        mod, _ = breaker_module
        cb = mod.CircuitBreaker("status-svc", failure_threshold=5, reset_timeout_seconds=15)
        status = await cb.status()
        assert status["name"] == "status-svc"
        assert status["state"] == "CLOSED"
        assert status["failure_threshold"] == 5
        assert status["failures"] == 0