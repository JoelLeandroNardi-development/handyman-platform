from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as redis_async
from fastapi import HTTPException

from tests.service_loader import load_service_app_module

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-helpers")
os.environ.setdefault("JWT_ALGORITHM", "HS256")


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
        "clients/redis_client",
        package_name="gateway_service_test_app",
        reload_modules=True,
    )
    breaker_module = load_service_app_module(
        "gateway-service",
        "breakers/breaker",
        package_name="gateway_service_test_app",
    )
    rbac_module = load_service_app_module(
        "gateway-service",
        "utils/rbac",
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


@pytest.fixture
def helpers_module(monkeypatch):
    """Load the gateway helpers module with fake Redis and stubbed clients."""
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
        "clients/redis_client",
        package_name="gateway_helpers_test_app",
        reload_modules=True,
    )
    load_service_app_module(
        "gateway-service",
        "breakers/breaker",
        package_name="gateway_helpers_test_app",
    )
    load_service_app_module(
        "gateway-service",
        "config",
        package_name="gateway_helpers_test_app",
    )
    load_service_app_module(
        "gateway-service",
        "clients",
        package_name="gateway_helpers_test_app",
    )
    helpers_mod = load_service_app_module(
        "gateway-service",
        "utils/helpers",
        package_name="gateway_helpers_test_app",
    )
    return helpers_mod


@pytest.mark.unit
class TestUserEmail:

    def test_returns_sub(self, helpers_module):
        assert helpers_module._user_email({"sub": "u@ex.com"}) == "u@ex.com"

    def test_raises_when_sub_missing(self, helpers_module):
        with pytest.raises(HTTPException) as exc:
            helpers_module._user_email({})
        assert exc.value.status_code == 401

    def test_returns_string_for_numeric_sub(self, helpers_module):
        assert helpers_module._user_email({"sub": 42}) == "42"


@pytest.mark.unit
class TestHasRole:

    def test_has_role_case_insensitive(self, helpers_module):
        assert helpers_module._has_role({"roles": ["Admin"]}, "admin") is True

    def test_has_role_returns_false_when_absent(self, helpers_module):
        assert helpers_module._has_role({"roles": ["user"]}, "admin") is False

    def test_has_role_returns_false_for_empty_roles(self, helpers_module):
        assert helpers_module._has_role({}, "admin") is False


@pytest.mark.unit
class TestAuthUserHasAnyRole:

    def test_matching_roles(self, helpers_module):
        assert helpers_module._auth_user_has_any_role({"roles": ["handyman"]}, ["handyman", "admin"]) is True

    def test_disjoint_roles(self, helpers_module):
        assert helpers_module._auth_user_has_any_role({"roles": ["user"]}, ["admin"]) is False

    def test_empty_auth_roles(self, helpers_module):
        assert helpers_module._auth_user_has_any_role({}, ["admin"]) is False


@pytest.mark.unit
class TestOverallStatus:

    def test_all_up(self, helpers_module):
        results = [{"status": "up"}, {"status": "up"}]
        assert helpers_module._overall_status(results) == "up"

    def test_degraded(self, helpers_module):
        results = [{"status": "up"}, {"status": "down"}]
        assert helpers_module._overall_status(results) == "degraded"

    def test_empty_list(self, helpers_module):
        assert helpers_module._overall_status([]) == "up"


@pytest.mark.unit
class TestBookingOwnedOrAdmin:

    @pytest.mark.asyncio
    async def test_admin_always_allowed(self, helpers_module):
        booking = {"user_email": "a@ex.com", "handyman_email": "b@ex.com"}
        helpers_module.get_booking = AsyncMock(return_value=booking)

        result = await helpers_module._booking_owned_or_admin(
            "b-1", {"sub": "admin@ex.com", "roles": ["admin"]}, "req-1"
        )

        assert result == booking

    @pytest.mark.asyncio
    async def test_user_owner_allowed(self, helpers_module):
        booking = {"user_email": "owner@ex.com", "handyman_email": "h@ex.com"}
        helpers_module.get_booking = AsyncMock(return_value=booking)

        result = await helpers_module._booking_owned_or_admin(
            "b-1", {"sub": "owner@ex.com", "roles": ["user"]}, "req-1"
        )

        assert result == booking

    @pytest.mark.asyncio
    async def test_handyman_owner_allowed(self, helpers_module):
        booking = {"user_email": "u@ex.com", "handyman_email": "hm@ex.com"}
        helpers_module.get_booking = AsyncMock(return_value=booking)

        result = await helpers_module._booking_owned_or_admin(
            "b-1", {"sub": "hm@ex.com", "roles": ["handyman"]}, "req-1"
        )

        assert result == booking

    @pytest.mark.asyncio
    async def test_non_owner_non_admin_forbidden(self, helpers_module):
        booking = {"user_email": "a@ex.com", "handyman_email": "b@ex.com"}
        helpers_module.get_booking = AsyncMock(return_value=booking)

        with pytest.raises(HTTPException) as exc:
            await helpers_module._booking_owned_or_admin(
                "b-1", {"sub": "stranger@ex.com", "roles": ["user"]}, "req-1"
            )

        assert exc.value.status_code == 403


@pytest.mark.unit
class TestGetAuthUserAfterRegister:

    @pytest.mark.asyncio
    async def test_returns_auth_user_on_success(self, helpers_module):
        auth_user = {"id": 1, "email": "u@ex.com", "roles": ["user"]}
        helpers_module.get_auth_user_by_email = AsyncMock(return_value=auth_user)

        result = await helpers_module._get_auth_user_after_register("u@ex.com", "req-1")

        assert result == auth_user

    @pytest.mark.asyncio
    async def test_wraps_http_error_as_502(self, helpers_module):
        helpers_module.get_auth_user_by_email = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="not found")
        )

        with pytest.raises(HTTPException) as exc:
            await helpers_module._get_auth_user_after_register("u@ex.com", "req-1")

        assert exc.value.status_code == 502