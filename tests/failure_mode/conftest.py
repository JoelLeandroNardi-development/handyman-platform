import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def failure_scenario_handler():
    async def handler_that_fails(payload):
        raise ValueError(f"Failed to process: {payload}")
    
    return handler_that_fails


@pytest.fixture
def handler_with_retry_count():
    class RetryTracker:
        def __init__(self):
            self.retry_count = 0
            self.calls = []
        
        async def handle(self, payload):
            self.calls.append(payload)
            self.retry_count += 1
            if self.retry_count < 3:
                raise ValueError("Simulated failure")
    
    return RetryTracker()


@pytest.fixture
def mock_dlq_publisher():
    return AsyncMock()


@pytest.fixture
def malformed_messages():
    return [
        b"not json",
        b"{ incomplete json",
        b"null",
        b"",
        None,
    ]


@pytest.fixture
def timeout_config():
    return {
        "handler_timeout_seconds": 5,
        "connection_timeout_seconds": 10,
        "rabbitmq_heartbeat": 60,
    }


@pytest.fixture
def dlq_config():
    return {
        "max_retries": 3,
        "retry_delay_ms": 5000,
        "dlq_queue_name": "booking_dlq",
        "dlq_enabled": True,
    }

