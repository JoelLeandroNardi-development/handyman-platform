from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Notification, NotificationPreference, PushDevice


async def create_notification_if_absent(
    db: AsyncSession,
    *,
    user_email: str,
    event_id: str,
    type: str,
    category: str,
    priority: str,
    title: str,
    body: str,
    entity_type: str | None,
    entity_id: str | None,
    action_url: str | None,
    payload: dict,
) -> Notification | None:
    stmt = (
        insert(Notification)
        .values(
            user_email=user_email,
            event_id=event_id,
            type=type,
            category=category,
            priority=priority,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            payload=payload,
            status="unread",
        )
        .on_conflict_do_nothing(
            index_elements=["user_email", "event_id", "type", "entity_id"]
        )
        .returning(Notification)
    )
    row = await db.execute(stmt)
    created = row.scalar_one_or_none()
    if created:
        await db.commit()
        return created
    await db.rollback()
    return None


async def list_notifications(
    db: AsyncSession,
    *,
    user_email: str,
    status: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[Sequence[Notification], str | None]:
    stmt = select(Notification).where(Notification.user_email == user_email)

    if status == "unread":
        stmt = stmt.where(Notification.status == "unread")
    elif status == "read":
        stmt = stmt.where(Notification.status == "read")
    elif status == "archived":
        stmt = stmt.where(Notification.status == "archived")
    else:
        stmt = stmt.where(Notification.status != "archived")

    if cursor:
        stmt = stmt.where(Notification.created_at < datetime.fromisoformat(cursor))

    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit + 1)
    rows = (await db.execute(stmt)).scalars().all()

    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[-2].created_at.isoformat()
        rows = rows[:limit]

    return rows, next_cursor


async def unread_count(db: AsyncSession, *, user_email: str) -> int:
    stmt = select(func.count()).select_from(Notification).where(
        Notification.user_email == user_email,
        Notification.status == "unread",
    )
    return int((await db.execute(stmt)).scalar_one())


async def mark_read(db: AsyncSession, *, user_email: str, notification_id: str) -> bool:
    stmt = (
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_email == user_email)
        .values(status="read", read_at=datetime.now(timezone.utc))
    )
    result = await db.execute(stmt)
    await db.commit()
    return (result.rowcount or 0) > 0


async def mark_all_read(db: AsyncSession, *, user_email: str) -> int:
    stmt = (
        update(Notification)
        .where(Notification.user_email == user_email, Notification.status == "unread")
        .values(status="read", read_at=datetime.now(timezone.utc))
    )
    result = await db.execute(stmt)
    await db.commit()
    return int(result.rowcount or 0)


async def archive_notification(db: AsyncSession, *, user_email: str, notification_id: str) -> bool:
    stmt = (
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_email == user_email)
        .values(status="archived", archived_at=datetime.now(timezone.utc))
    )
    result = await db.execute(stmt)
    await db.commit()
    return (result.rowcount or 0) > 0


async def get_preferences(db: AsyncSession, *, user_email: str) -> NotificationPreference:
    existing = await db.get(NotificationPreference, user_email)
    if existing:
        return existing

    pref = NotificationPreference(user_email=user_email)
    db.add(pref)
    await db.commit()
    await db.refresh(pref)
    return pref


async def update_preferences(db: AsyncSession, *, user_email: str, patch: dict) -> NotificationPreference:
    pref = await get_preferences(db, user_email=user_email)
    for key, value in patch.items():
        if value is not None:
            setattr(pref, key, value)
    await db.commit()
    await db.refresh(pref)
    return pref


async def upsert_push_device(
    db: AsyncSession,
    *,
    user_email: str,
    platform: str,
    device_token: str,
    device_name: str | None,
    app_version: str | None,
) -> PushDevice:
    existing = (
        await db.execute(select(PushDevice).where(PushDevice.device_token == device_token))
    ).scalar_one_or_none()

    if existing:
        existing.user_email = user_email
        existing.platform = platform
        existing.device_name = device_name
        existing.app_version = app_version
        existing.is_active = True
    else:
        existing = PushDevice(
            user_email=user_email,
            platform=platform,
            device_token=device_token,
            device_name=device_name,
            app_version=app_version,
            is_active=True,
        )
        db.add(existing)

    await db.commit()
    await db.refresh(existing)
    return existing


async def deactivate_push_device(db: AsyncSession, *, user_email: str, device_id: int) -> bool:
    stmt = (
        update(PushDevice)
        .where(PushDevice.id == device_id, PushDevice.user_email == user_email)
        .values(is_active=False)
    )
    result = await db.execute(stmt)
    await db.commit()
    return (result.rowcount or 0) > 0
