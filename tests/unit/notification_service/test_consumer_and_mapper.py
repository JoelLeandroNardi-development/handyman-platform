from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.constants import (
    EmailConstants,
    EventType,
    NotificationType,
    EVENT_ID_KEY,
    EVENT_TYPE_KEY,
)

@pytest.mark.unit
class TestNotificationMapper:
    def test_map_event_missing_type_or_id_returns_empty(self, mapper_module):
        assert mapper_module.map_event_to_notifications({EVENT_TYPE_KEY: EventType.SLOT_CONFIRMED}) == []
        assert mapper_module.map_event_to_notifications({EVENT_ID_KEY: "evt-1"}) == []

    def test_map_booking_requested_targets_handyman(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-1",
                EVENT_TYPE_KEY: EventType.BOOKING_REQUESTED,
                "data": {
                    "booking_id": "b1",
                    "user_email": EmailConstants.USER,
                    "handyman_email": EmailConstants.HANDYMAN,
                },
            }
        )
        assert len(intents) == 1
        assert intents[0]["user_email"] == EmailConstants.HANDYMAN
        assert intents[0]["type"] == "job.requested"

    def test_map_slot_confirmed_targets_both_parties(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-2",
                EVENT_TYPE_KEY: EventType.SLOT_CONFIRMED,
                "data": {
                    "booking_id": "b2",
                    "user_email": EmailConstants.USER,
                    "handyman_email": EmailConstants.HANDYMAN,
                },
            }
        )
        assert len(intents) == 2
        assert {intent["user_email"] for intent in intents} == {EmailConstants.USER, EmailConstants.HANDYMAN}
        assert {intent["type"] for intent in intents} == {"booking.confirmed", "job.confirmed"}

    def test_map_booking_completed_targets_both_parties(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-completed-1",
                EVENT_TYPE_KEY: EventType.BOOKING_COMPLETED,
                "data": {
                    "booking_id": "b-complete-1",
                    "user_email": EmailConstants.USER,
                    "handyman_email": EmailConstants.HANDYMAN,
                    "desired_start": "2026-03-20T10:00:00+00:00",
                },
            }
        )
        assert len(intents) == 2
        emails = {i["user_email"] for i in intents}
        assert emails == {EmailConstants.USER, EmailConstants.HANDYMAN}
        types = {i["type"] for i in intents}
        assert types == {NotificationType.BOOKING_COMPLETED, NotificationType.JOB_COMPLETED}
        for intent in intents:
            assert intent["entity_id"] == "b-complete-1"
            assert intent["category"] == "booking"

    def test_map_booking_completed_only_user_when_no_handyman(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-completed-2",
                EVENT_TYPE_KEY: EventType.BOOKING_COMPLETED,
                "data": {
                    "booking_id": "b-complete-2",
                    "user_email": EmailConstants.USER,
                },
            }
        )
        assert len(intents) == 1
        assert intents[0]["user_email"] == EmailConstants.USER
        assert intents[0]["type"] == NotificationType.BOOKING_COMPLETED

    def test_map_booking_completed_empty_when_no_parties(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-completed-3",
                EVENT_TYPE_KEY: EventType.BOOKING_COMPLETED,
                "data": {"booking_id": "b-complete-3"},
            }
        )
        assert intents == []

    def test_map_booking_rejected_targets_user(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-rejected-1",
                EVENT_TYPE_KEY: EventType.BOOKING_REJECTED,
                "data": {
                    "booking_id": "b-reject-1",
                    "user_email": EmailConstants.USER,
                    "handyman_email": EmailConstants.HANDYMAN,
                    "reason": "Conflicting schedule",
                },
            }
        )
        assert len(intents) == 1
        assert intents[0]["user_email"] == EmailConstants.USER
        assert intents[0]["type"] == NotificationType.BOOKING_REJECTED_BY_HANDYMAN
        assert intents[0]["priority"] == "high"
        assert intents[0]["payload"]["reason"] == "Conflicting schedule"
        assert intents[0]["entity_id"] == "b-reject-1"

    def test_map_booking_rejected_empty_when_no_user(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-rejected-2",
                EVENT_TYPE_KEY: EventType.BOOKING_REJECTED,
                "data": {"booking_id": "b-reject-2", "reason": "Unavailable"},
            }
        )
        assert intents == []

    def test_map_booking_completed_by_user_targets_handyman(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-cbu-1",
                EVENT_TYPE_KEY: EventType.BOOKING_COMPLETED_BY_USER,
                "data": {
                    "booking_id": "b-cbu-1",
                    "user_email": EmailConstants.USER,
                    "handyman_email": EmailConstants.HANDYMAN,
                },
            }
        )
        assert len(intents) == 1
        assert intents[0]["user_email"] == EmailConstants.HANDYMAN
        assert intents[0]["type"] == NotificationType.BOOKING_COMPLETED_BY_USER
        assert intents[0]["priority"] == "high"
        assert intents[0]["payload"]["user_email"] == EmailConstants.USER
        assert intents[0]["entity_id"] == "b-cbu-1"

    def test_map_booking_completed_by_user_empty_when_no_handyman(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-cbu-2",
                EVENT_TYPE_KEY: EventType.BOOKING_COMPLETED_BY_USER,
                "data": {"booking_id": "b-cbu-2", "user_email": EmailConstants.USER},
            }
        )
        assert intents == []

    def test_map_booking_completed_by_handyman_targets_user(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-cbh-1",
                EVENT_TYPE_KEY: EventType.BOOKING_COMPLETED_BY_HANDYMAN,
                "data": {
                    "booking_id": "b-cbh-1",
                    "user_email": EmailConstants.USER,
                    "handyman_email": EmailConstants.HANDYMAN,
                },
            }
        )
        assert len(intents) == 1
        assert intents[0]["user_email"] == EmailConstants.USER
        assert intents[0]["type"] == NotificationType.BOOKING_COMPLETED_BY_HANDYMAN
        assert intents[0]["priority"] == "high"
        assert intents[0]["payload"]["handyman_email"] == EmailConstants.HANDYMAN
        assert intents[0]["entity_id"] == "b-cbh-1"

    def test_map_booking_completed_by_handyman_empty_when_no_user(self, mapper_module):
        intents = mapper_module.map_event_to_notifications(
            {
                EVENT_ID_KEY: "evt-cbh-2",
                EVENT_TYPE_KEY: EventType.BOOKING_COMPLETED_BY_HANDYMAN,
                "data": {"booking_id": "b-cbh-2", "handyman_email": EmailConstants.HANDYMAN},
            }
        )
        assert intents == []

@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationConsumer:
    async def test_handle_event_no_intents(self, consumer_module, monkeypatch):
        called = False

        async def fake_publish(_email, _payload):
            nonlocal called
            called = True

        monkeypatch.setattr(consumer_module, "map_event_to_notifications", lambda _event: [])
        monkeypatch.setattr(consumer_module.hub, "publish", fake_publish)

        await consumer_module.handle_event(db=object(), event={"event_id": "evt-empty", "event_type": "unknown"})

        assert called is False

    async def test_handle_event_skips_disabled_category(self, consumer_module, monkeypatch):
        intent = {
            "user_email": EmailConstants.USER,
            "event_id": "evt-1",
            "type": NotificationType.BOOKING_CONFIRMED,
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

        await consumer_module.handle_event(db=object(), event={EVENT_ID_KEY: "evt-1", EVENT_TYPE_KEY: EventType.SLOT_CONFIRMED})

    async def test_handle_event_persists_and_publishes(self, consumer_module, monkeypatch):
        published: list[tuple[str, dict]] = []

        intent = {
            "user_email": EmailConstants.USER,
            "event_id": "evt-2",
            "type": NotificationType.BOOKING_CONFIRMED,
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
            assert user_email == EmailConstants.USER
            return 3

        async def fake_publish(email, payload):
            published.append((email, payload))

        monkeypatch.setattr(consumer_module, "map_event_to_notifications", lambda _event: [intent])
        monkeypatch.setattr(consumer_module, "get_preferences", fake_get_preferences)
        monkeypatch.setattr(consumer_module, "category_enabled", lambda _pref, _category: True)
        monkeypatch.setattr(consumer_module, "create_notification_if_absent", fake_create_notification_if_absent)
        monkeypatch.setattr(consumer_module, "unread_count", fake_unread_count)
        monkeypatch.setattr(consumer_module.hub, "publish", fake_publish)

        await consumer_module.handle_event(db=object(), event={EVENT_ID_KEY: "evt-2", EVENT_TYPE_KEY: EventType.SLOT_CONFIRMED})

        assert len(published) == 1
        assert published[0][0] == EmailConstants.USER
        assert published[0][1]["type"] == NotificationType.CREATED
        assert published[0][1]["unread_count"] == 3

    async def test_handle_event_fanout_publishes_for_each_recipient(self, consumer_module, monkeypatch):
        published: list[tuple[str, dict]] = []

        intents = [
            {
                "user_email": EmailConstants.USER,
                "event_id": "evt-fanout-1",
                "type": NotificationType.BOOKING_COMPLETED,
                "category": "booking",
                "priority": "normal",
                "title": "Booking completed",
                "body": "done",
                "status": "unread",
                "entity_type": "booking",
                "entity_id": "b1",
                "action_url": "/bookings/b1",
                "payload": {"booking_id": "b1"},
                "created_at": datetime.now(timezone.utc),
                "read_at": None,
                "id": "notif-user-1",
            },
            {
                "user_email": EmailConstants.HANDY,
                "event_id": "evt-fanout-1",
                "type": NotificationType.JOB_COMPLETED,
                "category": "booking",
                "priority": "normal",
                "title": "Job completed",
                "body": "done",
                "status": "unread",
                "entity_type": "booking",
                "entity_id": "b1",
                "action_url": "/jobs/b1",
                "payload": {"booking_id": "b1"},
                "created_at": datetime.now(timezone.utc),
                "read_at": None,
                "id": "notif-handy-1",
            },
        ]

        async def fake_get_preferences(_db, *, user_email):
            return {"user_email": user_email}

        async def fake_create_notification_if_absent(_db, **kwargs):
            return kwargs

        async def fake_unread_count(_db, *, user_email):
            return 1 if user_email == EmailConstants.USER else 2

        async def fake_publish(email, payload):
            published.append((email, payload))

        monkeypatch.setattr(consumer_module, "map_event_to_notifications", lambda _event: intents)
        monkeypatch.setattr(consumer_module, "get_preferences", fake_get_preferences)
        monkeypatch.setattr(consumer_module, "category_enabled", lambda _pref, _category: True)
        monkeypatch.setattr(consumer_module, "create_notification_if_absent", fake_create_notification_if_absent)
        monkeypatch.setattr(consumer_module, "unread_count", fake_unread_count)
        monkeypatch.setattr(consumer_module.hub, "publish", fake_publish)

        await consumer_module.handle_event(db=object(), event={EVENT_ID_KEY: "evt-fanout-1", EVENT_TYPE_KEY: EventType.BOOKING_COMPLETED})

        assert len(published) == 2
        assert {email for email, _ in published} == {EmailConstants.USER, EmailConstants.HANDY}

    async def test_handle_event_duplicate_on_retry_has_no_side_effects(self, consumer_module, monkeypatch):
        publish_calls: list[tuple[str, dict]] = []
        unread_calls: list[str] = []

        intent = {
            "user_email": EmailConstants.USER,
            "event_id": "evt-dup-1",
            "type": NotificationType.BOOKING_REJECTED_BY_HANDYMAN,
            "category": "booking",
            "priority": "high",
            "title": "Booking rejected",
            "body": "rejected",
            "entity_type": "booking",
            "entity_id": "b-dup-1",
            "action_url": "/bookings/b-dup-1",
            "payload": {"booking_id": "b-dup-1", "reason": "busy"},
        }

        async def fake_get_preferences(_db, *, user_email):
            return {"user_email": user_email}

        async def fake_create_notification_if_absent(_db, **_kwargs):
            # Simulate idempotency in repository layer during retry: already written
            return None

        async def fake_unread_count(_db, *, user_email):
            unread_calls.append(user_email)
            return 99

        async def fake_publish(email, payload):
            publish_calls.append((email, payload))

        monkeypatch.setattr(consumer_module, "map_event_to_notifications", lambda _event: [intent])
        monkeypatch.setattr(consumer_module, "get_preferences", fake_get_preferences)
        monkeypatch.setattr(consumer_module, "category_enabled", lambda _pref, _category: True)
        monkeypatch.setattr(consumer_module, "create_notification_if_absent", fake_create_notification_if_absent)
        monkeypatch.setattr(consumer_module, "unread_count", fake_unread_count)
        monkeypatch.setattr(consumer_module.hub, "publish", fake_publish)

        await consumer_module.handle_event(db=object(), event={EVENT_ID_KEY: "evt-dup-1", EVENT_TYPE_KEY: EventType.BOOKING_REJECTED})

        assert unread_calls == []
        assert publish_calls == []