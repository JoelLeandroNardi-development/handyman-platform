from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unread", index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    action_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_notifications_recipient_event_type_entity",
            "user_email",
            "event_id",
            "type",
            "entity_id",
            unique=True,
        ),
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_email: Mapped[str] = mapped_column(String(320), primary_key=True)
    booking_in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    booking_push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    booking_email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    chat_in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    chat_push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    chat_email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    system_in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    system_push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    system_email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(20), nullable=True)


class PushDevice(Base):
    __tablename__ = "push_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    device_token: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    device_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
