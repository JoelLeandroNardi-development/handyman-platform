from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared.shared.events import build_event
from shared.shared.schemas.bookings import (
    BookingResponse,
    CancelBooking,
    CreateBooking,
    RejectBookingRequest,
)


@pytest.mark.unit
class TestBookingSchemas:

    def test_create_booking_schema_valid(self, sample_booking_data):
        payload = CreateBooking(**sample_booking_data)

        assert payload.user_email == sample_booking_data["user_email"]
        assert payload.handyman_email == sample_booking_data["handyman_email"]
        assert payload.desired_end > payload.desired_start

    def test_create_booking_schema_missing_required_field(self):
        with pytest.raises(ValidationError) as exc_info:
            CreateBooking(
                user_email="user@example.com",
                handyman_email="handyman@example.com",
                desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
            )

        assert "desired_start" in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid_start",
        ["not-a-date", "2026-13-45T25:61:61Z"],
    )
    def test_create_booking_schema_invalid_datetime(self, invalid_start):
        with pytest.raises(ValidationError):
            CreateBooking(
                user_email="user@example.com",
                handyman_email="handyman@example.com",
                desired_start=invalid_start,
                desired_end="2026-03-17T12:00:00Z",
                job_description="Fix leaky faucet",
            )

    def test_create_booking_schema_date_string_is_accepted(self):
        payload = CreateBooking(
            user_email="user@example.com",
            handyman_email="handyman@example.com",
            desired_start="2026-03-17",
            desired_end="2026-03-17T12:00:00Z",
            job_description="Fix leaky faucet",
        )

        assert payload.desired_start.year == 2026
        assert payload.desired_start.day == 17

    def test_booking_response_defaults(self):
        response = BookingResponse(
            booking_id="booking-123",
            status="PENDING",
            user_email="user@example.com",
            handyman_email="handyman@example.com",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert response.completed_by_user is False
        assert response.completed_by_handyman is False
        assert response.rejected_by_handyman is False
        assert response.completed_at is None

    def test_cancel_booking_default_reason(self):
        payload = CancelBooking()

        assert payload.reason == "user_requested"

    def test_reject_booking_request_requires_non_empty_reason(self):
        with pytest.raises(ValidationError):
            RejectBookingRequest(reason="")


@pytest.mark.unit
class TestEventSchemas:

    def test_event_has_required_fields(self):
        event = build_event(
            "booking.requested",
            {"booking_id": "booking-123"},
            source="booking-service",
            event_id="evt-123",
            occurred_at="2026-03-17T10:00:00+00:00",
        )

        assert event == {
            "event_id": "evt-123",
            "event_type": "booking.requested",
            "occurred_at": "2026-03-17T10:00:00+00:00",
            "source": "booking-service",
            "data": {"booking_id": "booking-123"},
        }

    def test_event_builder_generates_identifier_when_missing(self):
        event = build_event(
            "booking.confirm_requested",
            {"booking_id": "booking-456"},
            source="booking-service",
        )

        assert event["event_id"]
        assert event["source"] == "booking-service"
        assert event["data"]["booking_id"] == "booking-456"
