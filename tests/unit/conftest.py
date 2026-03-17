import pytest


@pytest.fixture
def booking_service_url():
    return "http://localhost:8001"


@pytest.fixture
def availability_service_url():
    return "http://localhost:8002"


@pytest.fixture
def match_service_url():
    return "http://localhost:8003"


@pytest.fixture
def handyman_service_url():
    return "http://localhost:8004"


@pytest.fixture
def auth_service_url():
    return "http://localhost:8000"


@pytest.fixture
def rabbit_url():
    return "amqp://guest:guest@localhost:5672/"


@pytest.fixture
def postgres_url():
    return "postgresql+asyncpg://test:test@localhost:5432/handyman_test"

