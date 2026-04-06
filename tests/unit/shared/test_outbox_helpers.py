from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shared.core.outbox.helpers import add_outbox_event

@pytest.mark.unit
class TestAddOutboxEvent:
    def test_adds_event_with_correct_fields(self):
        db = MagicMock()
        OutboxEvent = MagicMock()

        event = {
            "event_id": "evt-1",
            "event_type": "booking.completed",
            "some_data": "value",
        }

        add_outbox_event(db, OutboxEvent, event)

        OutboxEvent.assert_called_once_with(
            event_id="evt-1",
            event_type="booking.completed",
            routing_key="booking.completed",
            payload=event,
            status="PENDING",
        )
        db.add.assert_called_once()

    def test_routing_key_matches_event_type(self):
        db = MagicMock()
        OutboxEvent = MagicMock()

        event = {
            "event_id": "evt-2",
            "event_type": "slot.reserved",
        }

        add_outbox_event(db, OutboxEvent, event)

        call_kwargs = OutboxEvent.call_args.kwargs
        assert call_kwargs["routing_key"] == "slot.reserved"

    def test_status_is_always_pending(self):
        db = MagicMock()
        OutboxEvent = MagicMock()

        event = {
            "event_id": "evt-3",
            "event_type": "availability.updated",
        }

        add_outbox_event(db, OutboxEvent, event)

        call_kwargs = OutboxEvent.call_args.kwargs
        assert call_kwargs["status"] == "PENDING"

    def test_full_event_dict_passed_as_payload(self):
        db = MagicMock()
        OutboxEvent = MagicMock()

        event = {
            "event_id": "evt-4",
            "event_type": "handyman.updated",
            "email": "pro@example.com",
            "skills": ["plumbing"],
        }

        add_outbox_event(db, OutboxEvent, event)

        call_kwargs = OutboxEvent.call_args.kwargs
        assert call_kwargs["payload"] is event