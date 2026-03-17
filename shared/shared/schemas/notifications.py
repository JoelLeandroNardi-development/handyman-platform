from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationItem(BaseModel):
    id: str
    type: str
    category: str
    priority: str
    title: str
    body: str
    status: str
    entity_type: str | None = None
    entity_id: str | None = None
    action_url: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    read_at: datetime | None = None

    model_config = {"from_attributes": True}
