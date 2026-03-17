import json

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from ..clients import (
    archive_my_notification,
    delete_my_push_device,
    get_my_notification_preferences,
    get_my_unread_count,
    list_my_notifications,
    mark_all_my_notifications_read,
    mark_my_notification_read,
    register_my_push_device,
    update_my_notification_preferences,
)
from ..config import NOTIFICATION_SERVICE_URL
from ..security import get_current_user

router = APIRouter()


@router.get("/me/notifications", tags=["Notifications"])
async def get_notifications(
    request: Request,
    user=Depends(get_current_user),
    status: str | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(default=None),
):
    return await list_my_notifications(
        request_id=request.state.request_id,
        user_payload=user,
        status=status,
        limit=limit,
        cursor=cursor,
    )


@router.get("/me/notifications/unread-count", tags=["Notifications"])
async def get_unread_count(request: Request, user=Depends(get_current_user)):
    return await get_my_unread_count(request_id=request.state.request_id, user_payload=user)


@router.post("/me/notifications/{notification_id}/read", tags=["Notifications"])
async def mark_notification_read(notification_id: str, request: Request, user=Depends(get_current_user)):
    return await mark_my_notification_read(
        notification_id,
        request_id=request.state.request_id,
        user_payload=user,
    )


@router.post("/me/notifications/read-all", tags=["Notifications"])
async def mark_all_read(request: Request, user=Depends(get_current_user)):
    return await mark_all_my_notifications_read(request_id=request.state.request_id, user_payload=user)


@router.post("/me/notifications/{notification_id}/archive", tags=["Notifications"])
async def archive_notification(notification_id: str, request: Request, user=Depends(get_current_user)):
    return await archive_my_notification(
        notification_id,
        request_id=request.state.request_id,
        user_payload=user,
    )


@router.get("/me/notification-preferences", tags=["Notifications"])
async def get_preferences(request: Request, user=Depends(get_current_user)):
    return await get_my_notification_preferences(request_id=request.state.request_id, user_payload=user)


@router.put("/me/notification-preferences", tags=["Notifications"])
async def update_preferences(payload: dict, request: Request, user=Depends(get_current_user)):
    return await update_my_notification_preferences(
        payload,
        request_id=request.state.request_id,
        user_payload=user,
    )


@router.post("/me/push-devices", tags=["Notifications"])
async def register_push_device(payload: dict, request: Request, user=Depends(get_current_user)):
    return await register_my_push_device(payload, request_id=request.state.request_id, user_payload=user)


@router.delete("/me/push-devices/{device_id}", tags=["Notifications"])
async def delete_push_device(device_id: int, request: Request, user=Depends(get_current_user)):
    return await delete_my_push_device(device_id, request_id=request.state.request_id, user_payload=user)


@router.get("/me/notifications/stream", tags=["Notifications"])
async def stream_notifications(request: Request, user=Depends(get_current_user)):
    request_id = getattr(request.state, "request_id", None)
    headers: dict[str, str] = {
        "X-User-Roles": json.dumps(user.get("roles", [])),
    }
    if request_id:
        headers["X-Request-Id"] = request_id
    if user.get("sub"):
        headers["X-User-Sub"] = str(user["sub"])
        headers["X-User-Email"] = str(user["sub"])

    async def event_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "GET",
                f"{NOTIFICATION_SERVICE_URL}/me/notifications/stream",
                headers=headers,
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    if chunk:
                        yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
