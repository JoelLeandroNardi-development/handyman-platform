from __future__ import annotations

import os
import types
import sys

import pytest

from tests.service_loader import load_service_app_module

_PKG = "avail_helpers_test_app"

@pytest.fixture(scope="module")
def helpers_module():
    outbox_name = f"{_PKG}.infrastructure.outbox_worker"
    if outbox_name not in sys.modules:
        stub = types.ModuleType(outbox_name)
        stub.enqueue_domain_event = lambda *a, **kw: None
        sys.modules[outbox_name] = stub

    infra_pkg = f"{_PKG}.infrastructure"
    if infra_pkg not in sys.modules:
        pkg = types.ModuleType(infra_pkg)
        pkg.__path__ = []
        sys.modules[infra_pkg] = pkg

    load_service_app_module(
        "availability-service",
        "domain/events",
        package_name=_PKG,
        reload_modules=True,
    )

    load_service_app_module(
        "availability-service",
        "domain/schemas",
        package_name=_PKG,
    )

    return load_service_app_module(
        "availability-service",
        "application/helpers",
        package_name=_PKG,
    )

@pytest.fixture(scope="module")
def schemas_module():
    return sys.modules.get(f"{_PKG}.domain.schemas")

@pytest.mark.unit
class TestKeyHelpers:
    def test_res_key(self, helpers_module):
        assert helpers_module.res_key("booking-1") == "reservation:booking-1"

    def test_res_handyman_set(self, helpers_module):
        assert helpers_module.res_handyman_set("pro@x.com") == "reservations_by_handyman:pro@x.com"

    def test_avail_key(self, helpers_module):
        assert helpers_module.avail_key("h@x.com") == "availability:h@x.com"

@pytest.mark.unit
class TestParse:
    def test_parses_iso_string(self, helpers_module):
        dt = helpers_module.parse("2026-04-01T10:00:00+00:00")
        assert dt.hour == 10

    def test_parses_basic_iso(self, helpers_module):
        dt = helpers_module.parse("2026-04-01")
        assert dt.day == 1

@pytest.mark.unit
class TestSlotsPayload:
    def test_converts_slots(self, helpers_module, schemas_module):
        if schemas_module is None:
            pytest.skip("schemas module not loaded")

        Slot = schemas_module.AvailabilitySlot
        slots = [
            Slot(start="2026-04-01T10:00:00Z", end="2026-04-01T12:00:00Z"),
            Slot(start="2026-04-02T14:00:00Z", end="2026-04-02T16:00:00Z"),
        ]
        result = helpers_module.slots_payload(slots)
        assert len(result) == 2
        assert "start" in result[0]
        assert "end" in result[0]

    def test_empty_list(self, helpers_module):
        assert helpers_module.slots_payload([]) == []

    def test_none_input(self, helpers_module):
        assert helpers_module.slots_payload(None) == []

@pytest.mark.unit
class TestParseRawSlot:
    def test_valid_pipe_separated(self, helpers_module):
        result = helpers_module.parse_raw_slot("2026-04-01T10:00:00+00:00|2026-04-01T12:00:00+00:00")
        assert result is not None
        start, end = result
        assert start.hour == 10
        assert end.hour == 12

    def test_invalid_format_returns_none(self, helpers_module):
        assert helpers_module.parse_raw_slot("garbage") is None

    def test_missing_pipe_returns_none(self, helpers_module):
        assert helpers_module.parse_raw_slot("2026-04-01T10:00:00") is None