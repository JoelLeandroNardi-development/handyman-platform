from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from shared.core.messaging import events as events_module
from shared.core.messaging.events import build_event
from shared.core.db.session import create_db, make_get_db

@pytest.mark.unit
class TestEventBuilders:
    def test_build_event_with_explicit_fields(self):
        event = build_event(
            "booking.requested", {"booking_id": "b-1"},
            source="booking-service", event_id="evt-1",
            occurred_at="2026-03-17T10:00:00+00:00",
        )
        assert event == {
            "event_id": "evt-1",
            "event_type": "booking.requested",
            "occurred_at": "2026-03-17T10:00:00+00:00",
            "source": "booking-service",
            "data": {"booking_id": "b-1"},
        }

    def test_build_event_generates_defaults(self):
        event = build_event("booking.requested", {}, source="booking-service")
        assert event["event_id"]
        assert event["source"] == "booking-service"

    def test_utc_now_iso_returns_utc(self):
        value = events_module.utc_now_iso()
        assert "+00:00" in value or value.endswith("Z")

    def test_build_event_jsonable_without_encoder(self, monkeypatch):
        monkeypatch.setattr(events_module, "_jsonable_encoder", None)
        event = events_module.build_event_jsonable(
            "booking.requested",
            {"when": datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc)},
            source="booking-service", event_id="evt-1",
            occurred_at="2026-03-17T10:00:00+00:00",
        )
        assert event["event_id"] == "evt-1"
        assert isinstance(event["data"]["when"], datetime)

    def test_make_event_builder_uses_service_name(self):
        builder = events_module.make_event_builder("booking-service")
        event = builder("booking.requested", {"booking_id": "b1"})
        assert event["source"] == "booking-service"

@pytest.mark.unit
class TestDbSession:
    def test_create_db_requires_env_var(self, monkeypatch):
        monkeypatch.delenv("TEST_DB_URL", raising=False)
        with pytest.raises(RuntimeError):
            create_db("TEST_DB_URL")

    def test_create_db_returns_triple(self, monkeypatch):
        monkeypatch.setenv("TEST_DB_URL", "sqlite+aiosqlite:///:memory:")
        engine, session_local, base = create_db("TEST_DB_URL", echo=False)
        assert engine and session_local and base

    @pytest.mark.asyncio
    async def test_make_get_db_yields_session(self):
        session = object()

        class _Ctx:
            async def __aenter__(self):
                return session
            async def __aexit__(self, *a):
                return False

        get_db = make_get_db(lambda: _Ctx())
        yielded = [item async for item in get_db()]
        assert yielded == [session]