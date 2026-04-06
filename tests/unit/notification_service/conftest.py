from __future__ import annotations

import os

import pytest

from tests.service_loader import load_service_app_module

os.environ.setdefault("NOTIFICATION_DB", "sqlite+aiosqlite:///:memory:")

@pytest.fixture(scope="module")
def mapper_module():
    return load_service_app_module(
        "notification-service",
        "application/mappers",
        package_name="notification_service_app",
        reload_modules=True,
    )


@pytest.fixture(scope="module")
def consumer_module(mapper_module):
    return load_service_app_module(
        "notification-service",
        "infrastructure/consumer",
        package_name="notification_service_app",
    )