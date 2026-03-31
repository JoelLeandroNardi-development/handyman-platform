from __future__ import annotations

from typing import Any, TypedDict

class NotificationIntent(TypedDict):
    user_email: str
    event_id: str
    type: str
    category: str
    priority: str
    title: str
    body: str
    entity_type: str | None
    entity_id: str | None
    action_url: str | None
    payload: dict[str, Any]