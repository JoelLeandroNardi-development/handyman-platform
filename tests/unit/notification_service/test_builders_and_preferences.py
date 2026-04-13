from __future__ import annotations

import types
import sys

import pytest

from tests.constants import (
    EmailConstants,
    EventType,
    NOTIF_BUILDERS_TEST_PACKAGE,
    NOTIFICATION_SERVICE_DIR,
)
from tests.service_loader import load_service_app_module

_PKG = NOTIF_BUILDERS_TEST_PACKAGE

@pytest.fixture(scope="module")
def _bootstrap():
    load_service_app_module(
        NOTIFICATION_SERVICE_DIR,
        "domain/notification_types",
        package_name=_PKG,
        reload_modules=True,
    )

    models_name = f"{_PKG}.domain.models"
    if models_name not in sys.modules:
        stub = types.ModuleType(models_name)

        class NotificationPreference:
            def __init__(self, **kwargs):
                self.booking_in_app_enabled = kwargs.get("booking_in_app_enabled", True)
                self.chat_in_app_enabled = kwargs.get("chat_in_app_enabled", True)
                self.system_in_app_enabled = kwargs.get("system_in_app_enabled", True)

        stub.NotificationPreference = NotificationPreference
        sys.modules[models_name] = stub

    return True

@pytest.fixture(scope="module")
def builders_module(_bootstrap):
    return load_service_app_module(
        NOTIFICATION_SERVICE_DIR,
        "application/notification_builders",
        package_name=_PKG,
    )

@pytest.fixture(scope="module")
def event_mappers_module(_bootstrap):
    return load_service_app_module(
        NOTIFICATION_SERVICE_DIR,
        "application/notification_event_mappers",
        package_name=_PKG,
    )

@pytest.fixture(scope="module")
def preferences_module(_bootstrap):
    return load_service_app_module(
        NOTIFICATION_SERVICE_DIR,
        "application/preferences",
        package_name=_PKG,
    )

@pytest.mark.unit
class TestBookingIntent:
    def test_returns_notification_intent(self, builders_module):
        intent = builders_module.booking_intent(
            event_id="evt-1",
            user_email=EmailConstants.USER,
            type="job.requested",
            priority="normal",
            title="New request",
            body="Someone requested a booking.",
            booking_id="booking-1",
            action_prefix="jobs",
            payload={"key": "val"},
        )
        assert intent["user_email"] == EmailConstants.USER
        assert intent["category"] == "booking"
        assert intent["action_url"] == "/jobs/booking-1"

    def test_no_booking_id_means_no_action_url(self, builders_module):
        intent = builders_module.booking_intent(
            event_id="evt-2",
            user_email=EmailConstants.USER,
            type="test",
            priority="low",
            title="T",
            body="B",
            booking_id=None,
            action_prefix="jobs",
            payload={},
        )
        assert intent["action_url"] is None

@pytest.mark.unit
class TestSingleBookingNotification:
    def test_returns_one_intent(self, builders_module):
        result = builders_module.single_booking_notification(
            event_id="e1",
            recipient_email="a@b.com",
            type="t",
            priority="normal",
            title="T",
            body="B",
            booking_id="b1",
            action_prefix="bookings",
            payload={},
        )
        assert len(result) == 1
        assert result[0]["user_email"] == "a@b.com"

    def test_no_recipient_returns_empty(self, builders_module):
        result = builders_module.single_booking_notification(
            event_id="e2",
            recipient_email=None,
            type="t",
            priority="normal",
            title="T",
            body="B",
            booking_id="b2",
            action_prefix="bookings",
            payload={},
        )
        assert result == []

@pytest.mark.unit
class TestAppendBookingNotification:
    def test_appends_to_list(self, builders_module):
        intents = []
        builders_module.append_booking_notification(
            intents,
            recipient_email="u@example.com",
            event_id="e3",
            type="t",
            priority="high",
            title="T",
            body="B",
            booking_id="b3",
            action_prefix="jobs",
            payload={},
        )
        assert len(intents) == 1

    def test_skips_if_no_recipient(self, builders_module):
        intents = []
        builders_module.append_booking_notification(
            intents,
            recipient_email=None,
            event_id="e4",
            type="t",
            priority="high",
            title="T",
            body="B",
            booking_id="b4",
            action_prefix="jobs",
            payload={},
        )
        assert len(intents) == 0

@pytest.mark.unit
class TestPickPayload:
    def test_picks_existing_keys(self, builders_module):
        result = builders_module.pick_payload({"a": 1, "b": 2, "c": 3}, "a", "c")
        assert result == {"a": 1, "c": 3}

    def test_missing_keys_get_none(self, builders_module):
        result = builders_module.pick_payload({"a": 1}, "a", "missing")
        assert result == {"a": 1, "missing": None}

_SAMPLE_DATA = {
    "booking_id": "booking-42",
    "user_email": EmailConstants.USER,
    "handyman_email": EmailConstants.HANDYMAN,
    "desired_start": "2026-04-01T10:00:00Z",
    "desired_end": "2026-04-01T12:00:00Z",
    "reason": "schedule conflict",
}

@pytest.mark.unit
class TestEventMappers:
    @pytest.mark.parametrize("mapper_name, expected_type, expected_recipient_key", [
        ("booking_requested", "job.requested", "handyman_email"),
        ("slot_reserved", "booking.reserved", "user_email"),
        ("slot_rejected", "booking.rejected", "user_email"),
        ("slot_expired", "booking.expired", "user_email"),
        ("booking_rejected", "booking.rejected_by_handyman", "user_email"),
        ("booking_completed_by_user", "job.completion_requested", "handyman_email"),
        ("booking_completed_by_handyman", "booking.completion_requested", "user_email"),
    ])
    def test_single_recipient_mappers(self, event_mappers_module, mapper_name, expected_type, expected_recipient_key):
        fn = getattr(event_mappers_module, mapper_name)
        intents = fn("evt-1", _SAMPLE_DATA)
        assert len(intents) == 1
        assert intents[0]["type"] == expected_type
        assert intents[0]["user_email"] == _SAMPLE_DATA[expected_recipient_key]

    @pytest.mark.parametrize("mapper_name", [
        "slot_confirmed",
        "booking_released",
        "booking_completed",
    ])
    def test_dual_recipient_mappers(self, event_mappers_module, mapper_name):
        fn = getattr(event_mappers_module, mapper_name)
        intents = fn("evt-2", _SAMPLE_DATA)
        assert len(intents) == 2
        recipients = {i["user_email"] for i in intents}
        assert recipients == {EmailConstants.USER, EmailConstants.HANDYMAN}

    def test_event_mappers_dict_covers_all_events(self, event_mappers_module):
        mappers = event_mappers_module.EVENT_MAPPERS
        expected_events = {
            EventType.BOOKING_REQUESTED,
            EventType.SLOT_RESERVED,
            EventType.SLOT_CONFIRMED,
            EventType.SLOT_REJECTED,
            EventType.SLOT_EXPIRED,
            EventType.SLOT_RELEASED,
            EventType.BOOKING_CANCEL_REQUESTED,
            EventType.BOOKING_COMPLETED,
            EventType.BOOKING_REJECTED,
            EventType.BOOKING_COMPLETED_BY_USER,
            EventType.BOOKING_COMPLETED_BY_HANDYMAN,
        }
        assert set(mappers.keys()) == expected_events

    def test_all_mappers_callable(self, event_mappers_module):
        for name, fn in event_mappers_module.EVENT_MAPPERS.items():
            assert callable(fn), f"Mapper for '{name}' is not callable"

@pytest.mark.unit
class TestCategoryEnabled:
    def test_booking_category(self, preferences_module):
        pref_mod_name = f"{_PKG}.domain.models"
        Pref = sys.modules[pref_mod_name].NotificationPreference

        pref = Pref(booking_in_app_enabled=True)
        assert preferences_module.category_enabled(pref, "booking") is True

        pref = Pref(booking_in_app_enabled=False)
        assert preferences_module.category_enabled(pref, "booking") is False

    def test_chat_category(self, preferences_module):
        pref_mod_name = f"{_PKG}.domain.models"
        Pref = sys.modules[pref_mod_name].NotificationPreference

        pref = Pref(chat_in_app_enabled=True)
        assert preferences_module.category_enabled(pref, "chat") is True

        pref = Pref(chat_in_app_enabled=False)
        assert preferences_module.category_enabled(pref, "chat") is False

    def test_unknown_falls_back_to_system(self, preferences_module):
        pref_mod_name = f"{_PKG}.domain.models"
        Pref = sys.modules[pref_mod_name].NotificationPreference

        pref = Pref(system_in_app_enabled=True)
        assert preferences_module.category_enabled(pref, "anything_else") is True

        pref = Pref(system_in_app_enabled=False)
        assert preferences_module.category_enabled(pref, "unknown") is False