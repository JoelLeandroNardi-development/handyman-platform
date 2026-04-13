from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.constants import ErrorMessage, PayloadKey
from ...domain.schemas import (
    MarkAllReadResponse, 
    NotificationPreferencesResponse, 
    PushDeviceResponse, 
    UpdateNotificationPreferencesRequest, 
    RegisterPushDeviceRequest
)
from ...infrastructure.repository import (
    archive_notification,
    deactivate_push_device,
    mark_all_read,
    mark_read,
    update_preferences,
    upsert_push_device,
)

class NotificationCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def mark_notification_read(
        self,
        notification_id: str,
        email: str,
    ) -> dict:
        ok = await mark_read(self.db, user_email=email, notification_id=notification_id)
        if not ok:
            raise HTTPException(status_code=404, detail=ErrorMessage.NOTIFICATION_NOT_FOUND)
        return {PayloadKey.OK: True}

    async def mark_my_notifications_read(
        self,
        email: str,
    ) -> MarkAllReadResponse:
        updated = await mark_all_read(self.db, user_email=email)
        return MarkAllReadResponse(updated=updated)

    async def archive_my_notification(
        self,
        notification_id: str,
        email: str,
    ) -> dict:
        ok = await archive_notification(self.db, user_email=email, notification_id=notification_id)
        if not ok:
            raise HTTPException(status_code=404, detail=ErrorMessage.NOTIFICATION_NOT_FOUND)
        return {PayloadKey.OK: True}

    async def update_my_preferences(
        self,
        payload: UpdateNotificationPreferencesRequest,
        email: str,
    ) -> NotificationPreferencesResponse:
        pref = await update_preferences(self.db, user_email=email, patch=payload.model_dump())
        return NotificationPreferencesResponse.model_validate(pref)

    async def register_push_device(
        self,
        payload: RegisterPushDeviceRequest,
        email: str,
    ) -> PushDeviceResponse:
        device = await upsert_push_device(
            self.db,
            user_email=email,
            platform=payload.platform,
            device_token=payload.device_token,
            device_name=payload.device_name,
            app_version=payload.app_version,
        )
        return PushDeviceResponse.model_validate(device)

    async def delete_push_device(
        self,
        device_id: int,
        email: str,
    ) -> dict:
        ok = await deactivate_push_device(self.db, user_email=email, device_id=device_id)
        if not ok:
            raise HTTPException(status_code=404, detail=ErrorMessage.DEVICE_NOT_FOUND)
        return {PayloadKey.OK: True}