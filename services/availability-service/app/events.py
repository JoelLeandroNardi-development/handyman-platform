from __future__ import annotations

from shared.shared.events import build_event as _build_event

SERVICE_NAME = "availability-service"


def build_event(event_type: str, data: dict) -> dict:
    return _build_event(event_type, data, source=SERVICE_NAME)