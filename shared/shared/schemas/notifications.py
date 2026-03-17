from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    next_cursor: str | None = None


class UnreadCountResponse(BaseModel):
    count: int = Field(..., ge=0)


class MarkAllReadResponse(BaseModel):
    updated: int = Field(..., ge=0)


class NotificationPreferencesResponse(BaseModel):
    booking_in_app_enabled: bool = True
    booking_push_enabled: bool = True
    booking_email_enabled: bool = True
    chat_in_app_enabled: bool = True
    chat_push_enabled: bool = True
    chat_email_enabled: bool = False
    system_in_app_enabled: bool = True
    system_push_enabled: bool = False
    system_email_enabled: bool = True
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None
    locale: str | None = None

    model_config = {"from_attributes": True}


class UpdateNotificationPreferencesRequest(BaseModel):
    booking_in_app_enabled: bool | None = None
    booking_push_enabled: bool | None = None
    booking_email_enabled: bool | None = None
    chat_in_app_enabled: bool | None = None
    chat_push_enabled: bool | None = None
    chat_email_enabled: bool | None = None
    system_in_app_enabled: bool | None = None
    system_push_enabled: bool | None = None
    system_email_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None
    locale: str | None = None


class RegisterPushDeviceRequest(BaseModel):
    platform: Literal["web", "ios", "android"]
    device_token: str
    device_name: str | None = None
    app_version: str | None = None


class PushDeviceResponse(BaseModel):
    id: int
    user_email: str
    platform: str
    device_token: str
    device_name: str | None = None
    app_version: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
