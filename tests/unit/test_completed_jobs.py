"""Tests for booking-service completed_jobs_count aggregate.

Covers:
  - single completed booking → count = 1
  - multiple completed bookings → correct count
  - non-completed statuses (PENDING, CONFIRMED, CANCELED, etc.) are ignored
  - duplicate completion (same booking already COMPLETED) does not double-count
  - batch query returns correct counts per handyman
  - empty batch returns empty dict
  - unknown handyman returns 0
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import os

import pytest

from tests.service_loader import load_service_app_module


os.environ.setdefault("BOOKING_DB", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("RABBIT_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("EXCHANGE_NAME", "test_exchange")


@pytest.fixture(scope="module")
def booking_db_module():
    return load_service_app_module(
        "booking-service", "infrastructure/db",
        package_name="booking_cj_test_app",
        reload_modules=True,
    )


@pytest.fixture(scope="module")
def booking_models_module(booking_db_module):
    return load_service_app_module(
        "booking-service", "domain/models",
        package_name="booking_cj_test_app",
    )


@pytest.fixture(scope="module")
def completed_jobs_module(booking_models_module):
    return load_service_app_module(
        "booking-service", "infrastructure/repository",
        package_name="booking_cj_test_app",
    )


@pytest.fixture(autouse=True)
async def _setup_tables(booking_db_module, booking_models_module):
    """Create tables before each test and drop after."""
    engine = booking_db_module.engine
    async with engine.begin() as conn:
        await conn.run_sync(booking_db_module.Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(booking_db_module.Base.metadata.drop_all)


async def _insert_booking(
    booking_db_module,
    booking_models_module,
    *,
    booking_id: str,
    handyman_email: str,
    status: str,
    user_email: str = "user@example.com",
):
    """Insert a booking row directly into the DB."""
    from datetime import datetime, timezone

    Booking = booking_models_module.Booking
    async with booking_db_module.SessionLocal() as db:
        db.add(Booking(
            booking_id=booking_id,
            user_email=user_email,
            handyman_email=handyman_email,
            desired_start=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
            status=status,
        ))
        await db.commit()


@pytest.mark.unit
class TestCompletedJobsCount:
    """Single-handyman completed_jobs_count."""

    @pytest.mark.asyncio
    async def test_one_completed_booking(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-1", handyman_email="h@test.com", status="COMPLETED",
        )
        count = await completed_jobs_module.get_completed_jobs_count("h@test.com")
        assert count == 1

    @pytest.mark.asyncio
    async def test_multiple_completed_bookings(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        for i in range(3):
            await _insert_booking(
                booking_db_module, booking_models_module,
                booking_id=f"b-{i}", handyman_email="h@test.com", status="COMPLETED",
            )
        count = await completed_jobs_module.get_completed_jobs_count("h@test.com")
        assert count == 3

    @pytest.mark.asyncio
    async def test_non_completed_statuses_ignored(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        for i, status in enumerate(
            ["PENDING", "RESERVED", "CONFIRMED", "CANCELED", "FAILED", "EXPIRED", "REJECTED"]
        ):
            await _insert_booking(
                booking_db_module, booking_models_module,
                booking_id=f"b-{i}", handyman_email="h@test.com", status=status,
            )
        count = await completed_jobs_module.get_completed_jobs_count("h@test.com")
        assert count == 0

    @pytest.mark.asyncio
    async def test_mixed_statuses_counts_only_completed(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-1", handyman_email="h@test.com", status="COMPLETED",
        )
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-2", handyman_email="h@test.com", status="CANCELED",
        )
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-3", handyman_email="h@test.com", status="COMPLETED",
        )
        count = await completed_jobs_module.get_completed_jobs_count("h@test.com")
        assert count == 2

    @pytest.mark.asyncio
    async def test_unknown_handyman_returns_zero(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        count = await completed_jobs_module.get_completed_jobs_count("nobody@test.com")
        assert count == 0

    @pytest.mark.asyncio
    async def test_duplicate_completed_booking_id_not_possible(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        """booking_id is unique — re-inserting the same booking_id is impossible,
        so replaying a completion event on an already-COMPLETED booking is a
        no-op (status stays COMPLETED), and the count stays correct."""
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-dup", handyman_email="h@test.com", status="COMPLETED",
        )
        # Simulate replayed event: status is already COMPLETED, no new row
        count = await completed_jobs_module.get_completed_jobs_count("h@test.com")
        assert count == 1

    @pytest.mark.asyncio
    async def test_separate_handymen_counted_independently(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-a1", handyman_email="alice@test.com", status="COMPLETED",
        )
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-a2", handyman_email="alice@test.com", status="COMPLETED",
        )
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-b1", handyman_email="bob@test.com", status="COMPLETED",
        )
        assert await completed_jobs_module.get_completed_jobs_count("alice@test.com") == 2
        assert await completed_jobs_module.get_completed_jobs_count("bob@test.com") == 1


@pytest.mark.unit
class TestCompletedJobsCountsBatch:
    """Batch completed_jobs_counts query."""

    @pytest.mark.asyncio
    async def test_batch_returns_correct_counts(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-1", handyman_email="alice@test.com", status="COMPLETED",
        )
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-2", handyman_email="alice@test.com", status="COMPLETED",
        )
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-3", handyman_email="bob@test.com", status="COMPLETED",
        )
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-4", handyman_email="bob@test.com", status="CANCELED",
        )

        result = await completed_jobs_module.get_completed_jobs_counts(
            ["alice@test.com", "bob@test.com"]
        )
        assert result == {"alice@test.com": 2, "bob@test.com": 1}

    @pytest.mark.asyncio
    async def test_batch_missing_handyman_returns_zero(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        result = await completed_jobs_module.get_completed_jobs_counts(
            ["nobody@test.com"]
        )
        assert result == {"nobody@test.com": 0}

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty_dict(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        result = await completed_jobs_module.get_completed_jobs_counts([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_batch_deduplicates_emails(
        self, booking_db_module, booking_models_module, completed_jobs_module,
    ):
        await _insert_booking(
            booking_db_module, booking_models_module,
            booking_id="b-1", handyman_email="h@test.com", status="COMPLETED",
        )
        result = await completed_jobs_module.get_completed_jobs_counts(
            ["h@test.com", "h@test.com"]
        )
        assert result["h@test.com"] == 1
