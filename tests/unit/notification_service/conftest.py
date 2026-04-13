from __future__ import annotations

import os

import pytest

from tests.constants import (
    ENV_NOTIFICATION_DB,
    IN_MEMORY_SQLITE_URL,
    NOTIFICATION_SERVICE_DIR,
    NOTIFICATION_SERVICE_PACKAGE,
)
from tests.service_loader import load_service_app_module

os.environ.setdefault(ENV_NOTIFICATION_DB, IN_MEMORY_SQLITE_URL)

@pytest.fixture(scope="module")
def mapper_module():
    return load_service_app_module(
        NOTIFICATION_SERVICE_DIR,
        "application/mappers",
        package_name=NOTIFICATION_SERVICE_PACKAGE,
        reload_modules=True,
    )


@pytest.fixture(scope="module")
def consumer_module(mapper_module):
    return load_service_app_module(
        NOTIFICATION_SERVICE_DIR,
        "infrastructure/consumer",
        package_name=NOTIFICATION_SERVICE_PACKAGE,
    )