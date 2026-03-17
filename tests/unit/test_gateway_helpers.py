from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as redis_async
from fastapi import HTTPException

from tests.service_loader import load_service_app_module


@pytest.fixture
def gateway_modules(monkeypatch):
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=None)
    fake_redis.set = AsyncMock(return_value=True)
    fake_redis.incr = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock(return_value=True)
    fake_redis.mget = AsyncMock(return_value=[None, None, None])
    fake_redis.pipeline = MagicMock()

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis_async, "from_url", lambda *args, **kwargs: fake_redis)

    load_service_app_module(
        "gateway-service",
        "redis_client",
        package_name="gateway_service_test_app",
        reload_modules=True,
    )
    breaker_module = load_service_app_module(
        "gateway-service",
        "breaker",
        package_name="gateway_service_test_app",
    )
    rbac_module = load_service_app_module(
        "gateway-service",
        "rbac",
        package_name="gateway_service_test_app",
    )
    breaker_module.redis_client = fake_redis
    return breaker_module, rbac_module, fake_redis


@pytest.mark.unit
class TestRequireRole:

    def test_require_role_allows_matching_role(self, gateway_modules):
        _, rbac_module, _ = gateway_modules

        assert rbac_module.require_role({"roles": ["Admin"]}, ["admin", "manager"]) is None

    def test_require_role_rejects_missing_roles(self, gateway_modules):
        _, rbac_module, _ = gateway_modules

        with pytest.raises(HTTPException) as exc_info:
            rbac_module.require_role({}, ["admin"])

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Roles missing in token"

    def test_require_role_rejects_disjoint_roles(self, gateway_modules):
        _, rbac_module, _ = gateway_modules

        with pytest.raises(HTTPException) as exc_info:
            rbac_module.require_role({"roles": ["customer"]}, ["admin"])

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Access forbidden for this role"


@pytest.mark.unit
class TestCircuitBreaker:

    @pytest.mark.asyncio
    async def test_allow_request_closed_allows(self, gateway_modules):
        breaker_module, _, fake_redis = gateway_modules
        fake_redis.get = AsyncMock(return_value="CLOSED")
        breaker = breaker_module.CircuitBreaker("booking")

        await breaker.allow_request()

    @pytest.mark.asyncio
    async def test_allow_request_open_without_timestamp_closes(self, gateway_modules):
        breaker_module, _, fake_redis = gateway_modules
        fake_redis.get = AsyncMock(side_effect=["OPEN", None])
        breaker = breaker_module.CircuitBreaker("booking")
        breaker.close = AsyncMock()

        await breaker.allow_request()

        breaker.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_allow_request_open_before_timeout_raises(self, gateway_modules, monkeypatch):
        breaker_module, _, fake_redis = gateway_modules
        fake_redis.get = AsyncMock(side_effect=["OPEN", "100.0"])
        monkeypatch.setattr(breaker_module.time, "time", lambda: 105.0)
        breaker = breaker_module.CircuitBreaker("booking", reset_timeout_seconds=15)

        with pytest.raises(breaker_module.CircuitBreakerOpen):
            await breaker.allow_request()

    @pytest.mark.asyncio
    async def test_allow_request_open_after_timeout_sets_half_open(self, gateway_modules, monkeypatch):
        breaker_module, _, fake_redis = gateway_modules
        fake_redis.get = AsyncMock(side_effect=["OPEN", "100.0"])
        fake_redis.set = AsyncMock(return_value=True)
        monkeypatch.setattr(breaker_module.time, "time", lambda: 120.0)
        breaker = breaker_module.CircuitBreaker("booking", reset_timeout_seconds=15)

        await breaker.allow_request()

        fake_redis.set.assert_awaited_once_with("cb:booking:state", "HALF_OPEN")

    @pytest.mark.asyncio
    async def test_record_success_closes_breaker(self, gateway_modules):
        breaker_module, _, _ = gateway_modules
        breaker = breaker_module.CircuitBreaker("booking")
        breaker.close = AsyncMock()

        await breaker.record_success()

        breaker.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_failure_from_half_open_reopens(self, gateway_modules):
        breaker_module, _, _ = gateway_modules
        breaker = breaker_module.CircuitBreaker("booking")
        breaker._get_state = AsyncMock(return_value="HALF_OPEN")
        breaker.open = AsyncMock()

        await breaker.record_failure()

        breaker.open.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_failure_sets_expiry_on_first_failure(self, gateway_modules):
        breaker_module, _, fake_redis = gateway_modules
        fake_redis.incr = AsyncMock(return_value=1)
        fake_redis.expire = AsyncMock(return_value=True)
        breaker = breaker_module.CircuitBreaker("booking", failure_threshold=5)
        breaker._get_state = AsyncMock(return_value="CLOSED")
        breaker.open = AsyncMock()

        await breaker.record_failure()

        fake_redis.expire.assert_awaited_once_with("cb:booking:failures", 60)
        breaker.open.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_record_failure_opens_at_threshold(self, gateway_modules):
        breaker_module, _, fake_redis = gateway_modules
        fake_redis.incr = AsyncMock(return_value=3)
        breaker = breaker_module.CircuitBreaker("booking", failure_threshold=3)
        breaker._get_state = AsyncMock(return_value="CLOSED")
        breaker.open = AsyncMock()

        await breaker.record_failure()

        breaker.open.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_open_writes_state_and_expiries(self, gateway_modules, monkeypatch):
        breaker_module, _, fake_redis = gateway_modules
        fake_pipe = MagicMock()
        fake_pipe.set = MagicMock()
        fake_pipe.expire = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[])
        fake_redis.pipeline = MagicMock(return_value=fake_pipe)
        monkeypatch.setattr(breaker_module.time, "time", lambda: 123.45)
        breaker = breaker_module.CircuitBreaker("booking", reset_timeout_seconds=15)

        await breaker.open()

        fake_pipe.set.assert_any_call("cb:booking:state", "OPEN")
        fake_pipe.set.assert_any_call("cb:booking:opened_at", "123.45")
        fake_pipe.expire.assert_any_call("cb:booking:state", 45)
        fake_pipe.expire.assert_any_call("cb:booking:opened_at", 45)
        fake_pipe.expire.assert_any_call("cb:booking:failures", 45)

    @pytest.mark.asyncio
    async def test_close_resets_state(self, gateway_modules):
        breaker_module, _, fake_redis = gateway_modules
        fake_pipe = MagicMock()
        fake_pipe.set = MagicMock()
        fake_pipe.delete = MagicMock()
        fake_pipe.expire = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[])
        fake_redis.pipeline = MagicMock(return_value=fake_pipe)
        breaker = breaker_module.CircuitBreaker("booking")

        await breaker.close()

        fake_pipe.set.assert_called_once_with("cb:booking:state", "CLOSED")
        fake_pipe.delete.assert_any_call("cb:booking:failures")
        fake_pipe.delete.assert_any_call("cb:booking:opened_at")
        fake_pipe.expire.assert_called_once_with("cb:booking:state", 3600)

    @pytest.mark.asyncio
    async def test_status_parses_redis_values(self, gateway_modules, monkeypatch):
        breaker_module, _, fake_redis = gateway_modules
        fake_redis.mget = AsyncMock(return_value=["OPEN", "3", "100.0"])
        monkeypatch.setattr(breaker_module.time, "time", lambda: 108.2)
        breaker = breaker_module.CircuitBreaker("booking", failure_threshold=5, reset_timeout_seconds=15)

        status = await breaker.status()

        assert status["name"] == "booking"
        assert status["state"] == "OPEN"
        assert status["failures"] == 3
        assert status["opened_at_epoch"] == 100.0
        assert status["open_for_seconds"] == 8.2