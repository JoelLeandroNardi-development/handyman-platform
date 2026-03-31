from __future__ import annotations

from typing import Any

from .notification_event_mappers import EVENT_MAPPERS
from ..domain.notification_types import NotificationIntent

def map_event_to_notifications(event: dict[str, Any]) -> list[NotificationIntent]:
    event_type = event.get("event_type")
    event_id = event.get("event_id")
    data = event.get("data") or {}

    if not event_type or not event_id:
        return []

    mapper = EVENT_MAPPERS.get(event_type)
    if mapper is None:
        return []

    return mapper(event_id, data)