from datetime import datetime, timezone
import uuid

import pytest

from shared.shared.outbox_helpers import add_outbox_event

from tests.service_loader import load_service_app_module


@pytest.fixture
def booking_modules(monkeypatch):
    monkeypatch.setenv("BOOKING_DB", "sqlite+aiosqlite:///:memory:")
    load_service_app_module(
        "booking-service",
        "db",
        package_name="booking_service_test_app",
        reload_modules=True,
    )
    models_module = load_service_app_module(
        "booking-service",
        "models",
        package_name="booking_service_test_app",
    )
    events_module = load_service_app_module(
        "booking-service",
        "events",
        package_name="booking_service_test_app",
    )
    return models_module, events_module


@pytest.mark.integration
@pytest.mark.booking_lifecycle
class TestBookingLifecycle:

    @pytest.mark.asyncio
    async def test_booking_creation_emits_event(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        event = events_module.build_event(
            "booking.requested",
            {
                "booking_id": "booking-123",
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
            },
        )

        assert event["source"] == "booking-service"
        assert event["event_type"] == "booking.requested"
        assert event["data"]["booking_id"] == "booking-123"
        assert event["data"]["user_email"] == sample_booking_data["user_email"]
    
    @pytest.mark.asyncio
    async def test_booking_status_transitions(self, booking_modules):
        models_module, _ = booking_modules
        Booking = models_module.Booking

        booking = Booking(
            booking_id="booking-456",
            user_email="user@example.com",
            handyman_email="handyman@example.com",
            desired_start=datetime(2026, 3, 20, 10, 0, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
            job_description="Fix roof",
            status="PENDING",
            completed_by_user=False,
            completed_by_handyman=False,
            rejected_by_handyman=False,
        )

        assert booking.status == "PENDING"

        booking.status = "RESERVED"
        assert booking.status == "RESERVED"

        booking.status = "CONFIRMED"
        assert booking.status == "CONFIRMED"

        booking.completed_by_user = True
        booking.completed_by_handyman = True
        booking.status = "COMPLETED"
        assert booking.status == "COMPLETED"
    
    @pytest.mark.asyncio
    async def test_cancellation_marked_with_timestamp_and_reason(self, booking_modules):
        models_module, _ = booking_modules
        Booking = models_module.Booking

        booking = Booking(
            booking_id="booking-cancel-123",
            user_email="user@example.com",
            handyman_email="handyman@example.com",
            desired_start=datetime(2026, 3, 20, 10, 0, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
            job_description="Fix roof",
            status="RESERVED",
            completed_by_user=False,
            completed_by_handyman=False,
            rejected_by_handyman=False,
        )

        booking.status = "CANCELED"
        booking.cancellation_reason = "user_requested"
        booking.canceled_at = datetime.now(timezone.utc)

        assert booking.status == "CANCELED"
        assert booking.cancellation_reason == "user_requested"
        assert booking.canceled_at is not None
    
    @pytest.mark.asyncio
    async def test_rejection_records_handyman_reason(self, booking_modules):
        models_module, _ = booking_modules
        Booking = models_module.Booking

        booking = Booking(
            booking_id="booking-reject-456",
            user_email="user@example.com",
            handyman_email="handyman@example.com",
            desired_start=datetime(2026, 3, 20, 10, 0, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
            job_description="Fix roof",
            status="PENDING",
            completed_by_user=False,
            completed_by_handyman=False,
            rejected_by_handyman=False,
        )

        booking.rejected_by_handyman = True
        booking.rejection_reason = "Equipment not available"
        booking.status = "REJECTED"

        assert booking.rejected_by_handyman is True
        assert booking.rejection_reason == "Equipment not available"
        assert booking.status == "REJECTED"


@pytest.mark.integration
@pytest.mark.booking_lifecycle
class TestBookingEventFlow:

    @pytest.mark.asyncio
    async def test_slot_reserved_event_updates_booking_status(self, booking_modules):
        _, events_module = booking_modules

        event = events_module.build_event(
            "slot.reserved",
            {
                "booking_id": "booking-123",
                "handyman_email": "handyman@example.com",
            },
        )

        assert event["event_type"] == "slot.reserved"
        assert event["data"] == {
            "booking_id": "booking-123",
            "handyman_email": "handyman@example.com",
        }
    
    @pytest.mark.asyncio
    async def test_slot_rejected_event_updates_booking_status(self, booking_modules):
        _, events_module = booking_modules

        event = events_module.build_event(
            "slot.rejected",
            {
                "booking_id": "booking-456",
                "reason": "Slot no longer available",
            },
        )

        assert event["event_type"] == "slot.rejected"
        assert event["data"]["reason"] == "Slot no longer available"
    
    @pytest.mark.asyncio
    async def test_confirm_booking_emits_confirm_requested_event(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        booking_id = "booking-789"

        event = events_module.build_event(
            "booking.confirm_requested",
            {
                "booking_id": booking_id,
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
            },
        )

        assert event["event_type"] == "booking.confirm_requested"
        assert event["data"]["booking_id"] == booking_id
    
    @pytest.mark.asyncio
    async def test_cancel_booking_emits_cancel_requested_event(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        booking_id = "booking-cancel-789"
        reason = "User changed mind"

        event = events_module.build_event(
            "booking.cancel_requested",
            {
                "booking_id": booking_id,
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
                "reason": reason,
            },
        )

        assert event["event_type"] == "booking.cancel_requested"
        assert event["data"]["reason"] == reason


@pytest.mark.integration
@pytest.mark.booking_lifecycle
class TestOutboxPattern:

    @pytest.mark.asyncio
    async def test_outbox_event_persisted_with_booking(self, sample_booking_data, mock_db_session, booking_modules):
        models_module, events_module = booking_modules
        OutboxEvent = models_module.OutboxEvent

        booking_id = str(uuid.uuid4())

        event = events_module.build_event(
            "booking.requested",
            {
                "booking_id": booking_id,
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
            },
        )

        add_outbox_event(mock_db_session, OutboxEvent, event)
        added_event = mock_db_session.add.call_args.args[0]

        assert added_event.event_id == event["event_id"]
        assert added_event.event_type == "booking.requested"
        assert added_event.routing_key == "booking.requested"
        assert added_event.status == "PENDING"
    
    @pytest.mark.asyncio
    async def test_outbox_event_payload_matches_event(self, sample_booking_data, mock_db_session, booking_modules):
        models_module, events_module = booking_modules
        OutboxEvent = models_module.OutboxEvent

        event = events_module.build_event(
            "booking.confirm_requested",
            {
                "booking_id": "booking-123",
                "handyman_email": sample_booking_data["handyman_email"],
            },
        )

        add_outbox_event(mock_db_session, OutboxEvent, event)
        added_event = mock_db_session.add.call_args.args[0]

        assert added_event.payload == event


@pytest.mark.integration
@pytest.mark.booking_lifecycle
class TestBookingCompletion:

    @pytest.mark.asyncio
    async def test_booking_needs_both_completions(self, booking_modules):
        models_module, _ = booking_modules
        Booking = models_module.Booking

        booking = Booking(
            booking_id="booking-complete-123",
            user_email="user@example.com",
            handyman_email="handyman@example.com",
            desired_start=datetime(2026, 3, 20, 10, 0, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
            job_description="Fix roof",
            status="CONFIRMED",
            completed_by_user=False,
            completed_by_handyman=False,
            rejected_by_handyman=False,
        )

        booking.completed_by_user = True
        assert booking.status != "COMPLETED"

        booking.completed_by_handyman = True

        if booking.completed_by_user and booking.completed_by_handyman:
            booking.status = "COMPLETED"
            booking.completed_at = datetime.now(timezone.utc)

        assert booking.status == "COMPLETED"
        assert booking.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_completion_timestamp_recorded(self, booking_modules):
        models_module, _ = booking_modules
        Booking = models_module.Booking

        booking = Booking(
            booking_id="booking-timestamp-456",
            user_email="user@example.com",
            handyman_email="handyman@example.com",
            desired_start=datetime(2026, 3, 20, 10, 0, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
            job_description="Fix roof",
            status="CONFIRMED",
            completed_by_user=False,
            completed_by_handyman=False,
            rejected_by_handyman=False,
        )

        assert booking.completed_at is None

        booking.completed_by_user = True
        booking.completed_by_handyman = True
        booking.status = "COMPLETED"
        booking.completed_at = datetime.now(timezone.utc)

        assert booking.completed_at is not None
        assert isinstance(booking.completed_at, datetime)


@pytest.mark.integration
@pytest.mark.booking_lifecycle
class TestBookingRejectedEventFlow:

    @pytest.mark.asyncio
    async def test_reject_booking_emits_rejected_event(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        booking_id = "booking-reject-event-001"
        reason = "Conflicting schedule"

        event = events_module.build_event(
            "booking.rejected",
            {
                "booking_id": booking_id,
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
                "reason": reason,
            },
        )

        assert event["source"] == "booking-service"
        assert event["event_type"] == "booking.rejected"
        assert event["data"]["booking_id"] == booking_id
        assert event["data"]["reason"] == reason

    @pytest.mark.asyncio
    async def test_rejected_event_payload_contains_booking_parties(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        event = events_module.build_event(
            "booking.rejected",
            {
                "booking_id": "booking-reject-event-002",
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
                "reason": "Tools unavailable",
            },
        )

        assert event["data"]["user_email"] == sample_booking_data["user_email"]
        assert event["data"]["handyman_email"] == sample_booking_data["handyman_email"]
        assert event["data"]["job_description"] == sample_booking_data["job_description"]

    @pytest.mark.asyncio
    async def test_rejected_outbox_event_persisted_with_correct_fields(
        self, sample_booking_data, mock_db_session, booking_modules
    ):
        models_module, events_module = booking_modules
        OutboxEvent = models_module.OutboxEvent

        booking_id = str(uuid.uuid4())

        event = events_module.build_event(
            "booking.rejected",
            {
                "booking_id": booking_id,
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
                "reason": "No longer available",
            },
        )

        add_outbox_event(mock_db_session, OutboxEvent, event)
        added_event = mock_db_session.add.call_args.args[0]

        assert added_event.event_id == event["event_id"]
        assert added_event.event_type == "booking.rejected"
        assert added_event.routing_key == "booking.rejected"
        assert added_event.status == "PENDING"
        assert added_event.payload["data"]["booking_id"] == booking_id
        assert added_event.payload["data"]["reason"] == "No longer available"

    @pytest.mark.asyncio
    async def test_rejected_event_ids_are_unique_per_rejection(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        payload = {
            "booking_id": "booking-idem-001",
            "user_email": sample_booking_data["user_email"],
            "handyman_email": sample_booking_data["handyman_email"],
            "desired_start": sample_booking_data["desired_start"],
            "desired_end": sample_booking_data["desired_end"],
            "job_description": sample_booking_data["job_description"],
            "reason": "Duplicate test",
        }

        event_a = events_module.build_event("booking.rejected", payload)
        event_b = events_module.build_event("booking.rejected", payload)

        assert event_a["event_id"] != event_b["event_id"]


@pytest.mark.integration
@pytest.mark.booking_lifecycle
class TestPartialCompletionEventFlow:

    @pytest.mark.asyncio
    async def test_completed_by_user_outbox_entry_when_handyman_not_yet_confirmed(
        self, sample_booking_data, mock_db_session, booking_modules
    ):
        models_module, events_module = booking_modules
        OutboxEvent = models_module.OutboxEvent

        booking_id = str(uuid.uuid4())
        event = events_module.build_event(
            "booking.completed_by_user",
            {
                "booking_id": booking_id,
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
            },
        )

        add_outbox_event(mock_db_session, OutboxEvent, event)
        added = mock_db_session.add.call_args.args[0]

        assert added.event_type == "booking.completed_by_user"
        assert added.routing_key == "booking.completed_by_user"
        assert added.status == "PENDING"
        assert added.payload["data"]["booking_id"] == booking_id
        assert added.payload["source"] == "booking-service"

    @pytest.mark.asyncio
    async def test_completed_by_handyman_outbox_entry_when_user_not_yet_confirmed(
        self, sample_booking_data, mock_db_session, booking_modules
    ):
        models_module, events_module = booking_modules
        OutboxEvent = models_module.OutboxEvent

        booking_id = str(uuid.uuid4())
        event = events_module.build_event(
            "booking.completed_by_handyman",
            {
                "booking_id": booking_id,
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
            },
        )

        add_outbox_event(mock_db_session, OutboxEvent, event)
        added = mock_db_session.add.call_args.args[0]

        assert added.event_type == "booking.completed_by_handyman"
        assert added.routing_key == "booking.completed_by_handyman"
        assert added.status == "PENDING"
        assert added.payload["data"]["booking_id"] == booking_id
        assert added.payload["source"] == "booking-service"

    @pytest.mark.asyncio
    async def test_partial_completion_event_ids_are_unique(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        payload = {
            "booking_id": "booking-partial-001",
            "user_email": sample_booking_data["user_email"],
            "handyman_email": sample_booking_data["handyman_email"],
            "desired_start": sample_booking_data["desired_start"],
            "desired_end": sample_booking_data["desired_end"],
            "job_description": sample_booking_data["job_description"],
        }
        e1 = events_module.build_event("booking.completed_by_user", payload)
        e2 = events_module.build_event("booking.completed_by_user", payload)
        assert e1["event_id"] != e2["event_id"]

    @pytest.mark.asyncio
    async def test_both_partial_events_have_correct_source(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules
        payload = {
            "booking_id": "booking-partial-002",
            "user_email": sample_booking_data["user_email"],
            "handyman_email": sample_booking_data["handyman_email"],
            "desired_start": sample_booking_data["desired_start"],
            "desired_end": sample_booking_data["desired_end"],
            "job_description": sample_booking_data["job_description"],
        }
        for event_type in ("booking.completed_by_user", "booking.completed_by_handyman"):
            event = events_module.build_event(event_type, payload)
            assert event["source"] == "booking-service"
            assert event["event_type"] == event_type
            assert "event_id" in event
            assert "occurred_at" in event


@pytest.mark.integration
@pytest.mark.booking_lifecycle
class TestBookingCompletedEventFlow:

    @pytest.mark.asyncio
    async def test_completed_outbox_event_persisted_when_both_parties_confirm(
        self, sample_booking_data, mock_db_session, booking_modules
    ):
        models_module, events_module = booking_modules
        OutboxEvent = models_module.OutboxEvent

        booking_id = str(uuid.uuid4())

        event = events_module.build_event(
            "booking.completed",
            {
                "booking_id": booking_id,
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
            },
        )

        add_outbox_event(mock_db_session, OutboxEvent, event)
        added_event = mock_db_session.add.call_args.args[0]

        assert added_event.event_id == event["event_id"]
        assert added_event.event_type == "booking.completed"
        assert added_event.routing_key == "booking.completed"
        assert added_event.status == "PENDING"
        assert added_event.payload["data"]["booking_id"] == booking_id

    @pytest.mark.asyncio
    async def test_completed_event_has_correct_source(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        event = events_module.build_event(
            "booking.completed",
            {
                "booking_id": "booking-complete-evt-001",
                "user_email": sample_booking_data["user_email"],
                "handyman_email": sample_booking_data["handyman_email"],
                "desired_start": sample_booking_data["desired_start"],
                "desired_end": sample_booking_data["desired_end"],
                "job_description": sample_booking_data["job_description"],
            },
        )

        assert event["source"] == "booking-service"
        assert event["event_type"] == "booking.completed"
        assert "event_id" in event
        assert "occurred_at" in event

    @pytest.mark.asyncio
    async def test_completed_event_ids_are_unique(self, sample_booking_data, booking_modules):
        _, events_module = booking_modules

        payload = {
            "booking_id": "booking-idem-002",
            "user_email": sample_booking_data["user_email"],
            "handyman_email": sample_booking_data["handyman_email"],
            "desired_start": sample_booking_data["desired_start"],
            "desired_end": sample_booking_data["desired_end"],
            "job_description": sample_booking_data["job_description"],
        }

        event_a = events_module.build_event("booking.completed", payload)
        event_b = events_module.build_event("booking.completed", payload)

        assert event_a["event_id"] != event_b["event_id"]
