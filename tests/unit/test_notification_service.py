from __future__ import annotations

import pytest

from tests.service_loader import load_service_app_module


events_module = load_service_app_module("notification-service", "events", package_name="notification_service_app", reload_modules=True)
consumer_module = load_service_app_module("notification-service", "event_consumer", package_name="notification_service_app", reload_modules=True)


@pytest.mark.unit
class TestNotificationEvents:
    def test_extract_email_recipients_deduplicates(self):
        data = {
            "user_email": "User@Example.com",
            "handyman_email": "user@example.com",
            "email": "another@example.com",
        }
        assert events_module.extract_email_recipients(data) == ["user@example.com", "another@example.com"]

    def test_extract_push_targets_deduplicates(self):
        data = {
            "user_push_topic": "User.Topic",
            "handyman_push_topic": "user.topic",
            "push_topic": "another topic",
        }
        assert events_module.extract_push_targets(data) == ["user-topic", "another-topic"]

    def test_extract_push_targets_falls_back_to_emails(self):
        data = {
            "user_email": "User@example.com",
            "handyman_email": "handy@example.com",
        }
        assert events_module.extract_push_targets(data) == ["user-example-com", "handy-example-com"]

    def test_channels_for_known_event(self):
        assert events_module.channels_for_event("slot.confirmed") == ["email", "push"]

    def test_render_notification_with_reason(self):
        title, body = events_module.render_notification("slot.rejected", {"booking_id": "b1", "reason": "no_slot"})
        assert title == "Booking rejected"
        assert "no_slot" in body


@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationConsumer:
    async def test_process_event_ignores_unknown_event(self, monkeypatch):
        email_calls = []
        push_calls = []

        async def fake_send_email(recipient, title, body, event_id, event_type):
            email_calls.append((recipient, event_id, event_type))

        async def fake_send_push(topic, title, body, event_id, event_type):
            push_calls.append((topic, event_id, event_type))

        monkeypatch.setattr(consumer_module, "send_email", fake_send_email)
        monkeypatch.setattr(consumer_module, "send_push", fake_send_push)

        await consumer_module.process_event(
            {
                "event_id": "evt-unknown",
                "event_type": "user.created",
                "data": {"user_email": "u@example.com", "booking_id": "b1"},
            }
        )

        assert email_calls == []
        assert push_calls == []

    async def test_process_event_fanout(self, monkeypatch):
        email_calls = []
        push_calls = []

        async def fake_send_email(recipient, title, body, event_id, event_type):
            email_calls.append((recipient, title, body, event_id, event_type))

        async def fake_send_push(topic, title, body, event_id, event_type):
            push_calls.append((topic, title, body, event_id, event_type))

        monkeypatch.setattr(consumer_module, "send_email", fake_send_email)
        monkeypatch.setattr(consumer_module, "send_push", fake_send_push)

        await consumer_module.process_event(
            {
                "event_id": "evt-fanout",
                "event_type": "slot.confirmed",
                "data": {
                    "booking_id": "b123",
                    "user_email": "user@example.com",
                    "handyman_email": "handy@example.com",
                    "user_push_topic": "user-notify",
                    "handyman_push_topic": "handy-notify",
                },
            }
        )

        assert len(email_calls) == 2
        assert {entry[0] for entry in email_calls} == {"user@example.com", "handy@example.com"}
        assert len(push_calls) == 2
        assert {entry[0] for entry in push_calls} == {"user-notify", "handy-notify"}

    async def test_process_event_push_falls_back_to_email_topics(self, monkeypatch):
        push_calls = []

        async def fake_send_push(topic, title, body, event_id, event_type):
            push_calls.append((topic, title, event_id, event_type))

        monkeypatch.setattr(consumer_module, "send_push", fake_send_push)

        await consumer_module.process_event(
            {
                "event_id": "evt-push-fallback",
                "event_type": "slot.reserved",
                "data": {
                    "booking_id": "b999",
                    "user_email": "user@example.com",
                    "handyman_email": "handy@example.com",
                },
            }
        )

        assert len(push_calls) == 2
        assert {entry[0] for entry in push_calls} == {"user-example-com", "handy-example-com"}

    async def test_process_event_skips_duplicate_event_id(self, monkeypatch):
        calls = []

        async def fake_send_push(topic, title, body, event_id, event_type):
            calls.append((topic, event_id))

        monkeypatch.setattr(consumer_module, "send_push", fake_send_push)

        payload = {
            "event_id": "evt-dup",
            "event_type": "slot.reserved",
            "data": {"booking_id": "b1", "push_topic": "job-b1"},
        }

        await consumer_module.process_event(payload)
        await consumer_module.process_event(payload)

        assert len(calls) == 1
