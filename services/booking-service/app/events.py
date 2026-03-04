from __future__ import annotations

from shared.shared.events import build_event_jsonable as _build_event

SERVICE_NAME = "booking-service"


def build_event(event_type: str, data: dict) -> dict:
    return _build_event(event_type, data, source=SERVICE_NAME)