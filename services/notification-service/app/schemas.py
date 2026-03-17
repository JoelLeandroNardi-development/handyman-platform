from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from shared.shared.schemas.notifications import NotificationItem


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    next_cursor: str | None = None


class UnreadCountResponse(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    updated: int


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
