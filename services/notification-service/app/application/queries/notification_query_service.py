from __future__ import annotations

import asyncio
import json

from fastapi import Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.sse import hub
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
        status_filter: str | None = Query(default=None, alias="status"),
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = Query(default=None),
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