from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import get_current_email
from .db import get_db
from .repository import (
    archive_notification,
    deactivate_push_device,
    get_preferences,
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
    update_preferences,
    upsert_push_device,
)
from .schemas import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    PushDeviceResponse,
    RegisterPushDeviceRequest,
    UnreadCountResponse,
    UpdateNotificationPreferencesRequest,
)
from .sse import hub


router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "notification-service"}


@router.get("/me/notifications", response_model=NotificationListResponse)
async def get_my_notifications(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    items, next_cursor = await list_notifications(
        db,
        user_email=email,
        status=status_filter,
        limit=limit,
        cursor=cursor,
    )
    return NotificationListResponse(items=items, next_cursor=next_cursor)


@router.get("/me/notifications/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    return UnreadCountResponse(count=await unread_count(db, user_email=email))


@router.post("/me/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await mark_read(db, user_email=email, notification_id=notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.post("/me/notifications/read-all", response_model=MarkAllReadResponse)
async def mark_my_notifications_read(
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> MarkAllReadResponse:
    updated = await mark_all_read(db, user_email=email)
    return MarkAllReadResponse(updated=updated)


@router.post("/me/notifications/{notification_id}/archive")
async def archive_my_notification(
    notification_id: str,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await archive_notification(db, user_email=email, notification_id=notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.get("/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_my_preferences(
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    pref = await get_preferences(db, user_email=email)
    return NotificationPreferencesResponse.model_validate(pref)


@router.put("/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_my_preferences(
    payload: UpdateNotificationPreferencesRequest,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    pref = await update_preferences(db, user_email=email, patch=payload.model_dump())
    return NotificationPreferencesResponse.model_validate(pref)


@router.post("/me/push-devices", response_model=PushDeviceResponse)
async def register_push_device(
    payload: RegisterPushDeviceRequest,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> PushDeviceResponse:
    device = await upsert_push_device(
        db,
        user_email=email,
        platform=payload.platform,
        device_token=payload.device_token,
        device_name=payload.device_name,
        app_version=payload.app_version,
    )
    return PushDeviceResponse.model_validate(device)


@router.delete("/me/push-devices/{device_id}")
async def delete_push_device(
    device_id: int,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await deactivate_push_device(db, user_email=email, device_id=device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}


@router.get("/me/notifications/stream")
async def stream_notifications(email: str = Depends(get_current_email)):
    async def event_generator():
        queue = await hub.subscribe(email)
        try:
            yield f"event: ready\ndata: {json.dumps({'ok': True})}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: {payload['type']}\ndata: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: ping\ndata: {json.dumps({'ok': True})}\n\n"
        finally:
            await hub.unsubscribe(email, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
