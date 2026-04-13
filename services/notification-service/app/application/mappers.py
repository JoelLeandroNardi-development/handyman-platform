from __future__ import annotations

from typing import Any

from .notification_event_mappers import EVENT_MAPPERS
from ..domain.constants import EventKey
from ..domain.notification_types import NotificationIntent

def map_event_to_notifications(event: dict[str, Any]) -> list[NotificationIntent]:
    event_type = event.get(EventKey.EVENT_TYPE)
    event_id = event.get(EventKey.EVENT_ID)
    data = event.get(EventKey.DATA) or {}

    if not event_type or not event_id:
        return []

    mapper = EVENT_MAPPERS.get(event_type)
    if mapper is None:
        return []

    return mapper(event_id, data)