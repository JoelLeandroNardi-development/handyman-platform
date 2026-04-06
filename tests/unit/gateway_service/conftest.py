from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as redis_async

from tests.service_loader import load_service_app_module

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-gateway")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

def _make_fake_redis():
    fake = MagicMock()
    fake.get = AsyncMock(return_value=None)
    fake.set = AsyncMock(return_value=True)
    fake.incr = AsyncMock(return_value=1)
    fake.expire = AsyncMock(return_value=True)
    fake.mget = AsyncMock(return_value=[None, None, None])
    fake.pipeline = MagicMock()
    return fake

@pytest.fixture
def gateway_modules(monkeypatch):
    fake_redis = _make_fake_redis()
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

@pytest.fixture
def helpers_module(monkeypatch):
    fake_redis = _make_fake_redis()
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
    return load_service_app_module(
        "gateway-service",
        "utils/helpers",
        package_name="gateway_helpers_test_app",
    )

@pytest.fixture
def security_module(monkeypatch):
    fake_redis = _make_fake_redis()
    monkeypatch.setattr(redis_async, "from_url", lambda *args, **kwargs: fake_redis)

    load_service_app_module(
        "gateway-service",
        "clients/redis_client",
        package_name="gateway_sse_test_app",
        reload_modules=True,
    )
    return load_service_app_module(
        "gateway-service",
        "utils/security",
        package_name="gateway_sse_test_app",
    )