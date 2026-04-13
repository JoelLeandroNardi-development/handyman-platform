from __future__ import annotations

import asyncio
import json
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.sse import hub
from ...domain.constants import HttpHeader, PayloadKey, SseEvent, SseSetting
from ...domain.schemas import NotificationListResponse, NotificationPreferencesResponse, UnreadCountResponse
from ...infrastructure.repository import (
    get_preferences,
    list_notifications,
    unread_count,
)

class NotificationQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_my_notifications(
        self,
        email: str,
        status_filter: str | None,
        limit: int,
        cursor: str | None,
    ) -> NotificationListResponse:
        items, next_cursor = await list_notifications(
            self.db,
            user_email=email,
            status=status_filter,
            limit=limit,
            cursor=cursor,
        )
        return NotificationListResponse(items=items, next_cursor=next_cursor)

    async def get_unread_count(
        self,
        email: str
    ) -> UnreadCountResponse:
        return UnreadCountResponse(count=await unread_count(self.db, user_email=email))

    async def get_my_preferences(
        self,
        email: str
    ) -> NotificationPreferencesResponse:
        pref = await get_preferences(self.db, user_email=email)
        return NotificationPreferencesResponse.model_validate(pref)

    async def stream_notifications(email: str):
        async def event_generator():
            queue = await hub.subscribe(email)
            try:
                yield f"event: {SseEvent.READY}\ndata: {json.dumps({PayloadKey.OK: True})}\n\n"
                while True:
                    try:
                        payload = await asyncio.wait_for(queue.get(), timeout=int(SseSetting.HEARTBEAT_INTERVAL_SECONDS))
                        yield f"event: {payload[PayloadKey.TYPE]}\ndata: {json.dumps(payload)}\n\n"
                    except asyncio.TimeoutError:
                        yield f"event: {SseEvent.PING}\ndata: {json.dumps({PayloadKey.OK: True})}\n\n"
            finally:
                await hub.unsubscribe(email, queue)

        return StreamingResponse(
            event_generator(),
            media_type=SseSetting.MEDIA_TYPE,
            headers={
                HttpHeader.CACHE_CONTROL: HttpHeader.CACHE_CONTROL_VALUE,
                HttpHeader.CONNECTION: HttpHeader.CONNECTION_VALUE,
                HttpHeader.X_ACCEL_BUFFERING: HttpHeader.X_ACCEL_BUFFERING_VALUE,
            },
        )