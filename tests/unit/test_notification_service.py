from __future__ import annotations

from datetime import datetime, timezone
import os

import pytest

from tests.service_loader import load_service_app_module


os.environ.setdefault("NOTIFICATION_DB", "postgresql+asyncpg://admin:admin@localhost:5432/notification_db")


mapper_module = load_service_app_module("notification-service", "mapper", package_name="notification_service_app", reload_modules=True)
consumer_module = load_service_app_module("notification-service", "consumer", package_name="notification_service_app", reload_modules=True)


@pytest.mark.unit
class TestNotificationMapper:
    def test_map_event_missing_type_or_id_returns_empty(self):
        assert mapper_module.map_event_to_notifications({"event_type": "slot.confirmed"}) == []
        assert mapper_module.map_event_to_notifications({"event_id": "evt-1"}) == []

    def test_map_booking_requested_targets_handyman(self):
        intents = mapper_module.map_event_to_notifications(
            {
                "event_id": "evt-1",
                "event_type": "booking.requested",
                "data": {
                    "booking_id": "b1",
                    "user_email": "user@example.com",
                    "handyman_email": "handy@example.com",
                },
            }
        )
        assert len(intents) == 1
        assert intents[0]["user_email"] == "handy@example.com"
        assert intents[0]["type"] == "job_requested"

    def test_map_slot_confirmed_targets_both_parties(self):
        intents = mapper_module.map_event_to_notifications(
            {
                "event_id": "evt-2",
                "event_type": "slot.confirmed",
                "data": {
                    "booking_id": "b2",
                    "user_email": "user@example.com",
                    "handyman_email": "handy@example.com",
                },
            }
        )
        assert len(intents) == 2
        assert {intent["user_email"] for intent in intents} == {"user@example.com", "handy@example.com"}
        assert {intent["type"] for intent in intents} == {"booking_confirmed", "job_confirmed"}


@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationConsumer:
    async def test_handle_event_no_intents(self, monkeypatch):
        called = False

        async def fake_publish(_email, _payload):
            nonlocal called
            called = True

        monkeypatch.setattr(consumer_module, "map_event_to_notifications", lambda _event: [])
        monkeypatch.setattr(consumer_module.hub, "publish", fake_publish)

        await consumer_module.handle_event(db=object(), event={"event_id": "evt-empty", "event_type": "unknown"})

        assert called is False

    async def test_handle_event_skips_disabled_category(self, monkeypatch):
        intent = {
            "user_email": "user@example.com",
            "event_id": "evt-1",
            "type": "booking_confirmed",
            "category": "booking",
            "priority": "high",
            "title": "Booking confirmed",
            "body": "ok",
            "entity_type": "booking",
            "entity_id": "b1",
            "action_url": "/bookings/b1",
            "payload": {"booking_id": "b1"},
        }

        async def fake_get_preferences(_db, *, user_email):
            return {"user_email": user_email}

        async def fake_create_notification_if_absent(_db, **_kwargs):
            raise AssertionError("create_notification_if_absent should not be called")

        monkeypatch.setattr(consumer_module, "map_event_to_notifications", lambda _event: [intent])
        monkeypatch.setattr(consumer_module, "get_preferences", fake_get_preferences)
        monkeypatch.setattr(consumer_module, "category_enabled", lambda _pref, _category: False)
        monkeypatch.setattr(consumer_module, "create_notification_if_absent", fake_create_notification_if_absent)

        await consumer_module.handle_event(db=object(), event={"event_id": "evt-1", "event_type": "slot.confirmed"})

    async def test_handle_event_persists_and_publishes(self, monkeypatch):
        published: list[tuple[str, dict]] = []

        intent = {
            "user_email": "user@example.com",
            "event_id": "evt-2",
            "type": "booking_confirmed",
            "category": "booking",
            "priority": "high",
            "title": "Booking confirmed",
            "body": "ok",
            "status": "unread",
            "entity_type": "booking",
            "entity_id": "b2",
            "action_url": "/bookings/b2",
            "payload": {"booking_id": "b2"},
            "created_at": datetime.now(timezone.utc),
            "read_at": None,
            "id": "notif-1",
        }

        async def fake_get_preferences(_db, *, user_email):
            return {"user_email": user_email}

        async def fake_create_notification_if_absent(_db, **kwargs):
            return dict(intent, **kwargs)

        async def fake_unread_count(_db, *, user_email):
            assert user_email == "user@example.com"
            return 3

        async def fake_publish(email, payload):
            published.append((email, payload))

        monkeypatch.setattr(consumer_module, "map_event_to_notifications", lambda _event: [intent])
        monkeypatch.setattr(consumer_module, "get_preferences", fake_get_preferences)
        monkeypatch.setattr(consumer_module, "category_enabled", lambda _pref, _category: True)
        monkeypatch.setattr(consumer_module, "create_notification_if_absent", fake_create_notification_if_absent)
        monkeypatch.setattr(consumer_module, "unread_count", fake_unread_count)
        monkeypatch.setattr(consumer_module.hub, "publish", fake_publish)

        await consumer_module.handle_event(db=object(), event={"event_id": "evt-2", "event_type": "slot.confirmed"})

        assert len(published) == 1
        assert published[0][0] == "user@example.com"
        assert published[0][1]["type"] == "notification.created"
        assert published[0][1]["unread_count"] == 3
