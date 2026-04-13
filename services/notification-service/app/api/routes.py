from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.commands.notification_command_service import NotificationCommandService
from ..application.queries.notification_query_service import NotificationQueryService
from ..domain.schemas import (
    MarkAllReadResponse, NotificationListResponse, NotificationPreferencesResponse, 
    UnreadCountResponse, PushDeviceResponse, RegisterPushDeviceRequest, UpdateNotificationPreferencesRequest
)
from ..domain.constants import QUERY_STATUS_ALIAS
from ..infrastructure.auth import get_current_email
from ..infrastructure.config import HEALTH_OK_KEY, HEALTH_SERVICE_KEY, SERVICE_NAME
from ..infrastructure.db import get_db

router = APIRouter()

@router.get("/health")
async def health() -> dict:
    return {HEALTH_OK_KEY: True, HEALTH_SERVICE_KEY: SERVICE_NAME}

@router.get("/me/notifications", response_model=NotificationListResponse)
async def get_my_notifications(
    status_filter: str | None = Query(default=None, alias=QUERY_STATUS_ALIAS),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    return await NotificationQueryService(db).get_my_notifications(email, status_filter, limit, cursor)

@router.get("/me/notifications/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    return await NotificationQueryService(db).get_unread_count(email)

@router.get("/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_my_preferences(
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    return await NotificationQueryService(db).get_my_preferences(email)

@router.get("/me/notifications/stream")
async def stream_notifications(email: str = Depends(get_current_email)):
    return await NotificationQueryService.stream_notifications(email)

@router.post("/me/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await NotificationCommandService(db).mark_notification_read(notification_id, email)

@router.post("/me/notifications/read-all", response_model=MarkAllReadResponse)
async def mark_my_notifications_read(
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> MarkAllReadResponse:
    return await NotificationCommandService(db).mark_my_notifications_read(email)

@router.post("/me/notifications/{notification_id}/archive")
async def archive_my_notification(
    notification_id: str,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await NotificationCommandService(db).archive_my_notification(notification_id, email)

@router.post("/me/push-devices", response_model=PushDeviceResponse)
async def register_push_device(
    payload: RegisterPushDeviceRequest,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> PushDeviceResponse:
    return await NotificationCommandService(db).register_push_device(payload, email)

@router.put("/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_my_preferences(
    payload: UpdateNotificationPreferencesRequest,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    return await NotificationCommandService(db).update_my_preferences(payload, email)

@router.delete("/me/push-devices/{device_id}")
async def delete_push_device(
    device_id: int,
    email: str = Depends(get_current_email),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await NotificationCommandService(db).delete_push_device(device_id, email)