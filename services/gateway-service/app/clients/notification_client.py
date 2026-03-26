from .base_client import _call_with_breaker
from ..breakers.circuit_breakers import cb_notification
from ..config import NOTIFICATION_SERVICE_URL


async def list_my_notifications(
    request_id: str | None = None,
    user_payload: dict | None = None,
    status: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
):
    qs = f"limit={limit}"
    if status:
        qs += f"&status={status}"
    if cursor:
        qs += f"&cursor={cursor}"
    return await _call_with_breaker(
        cb_notification,
        "GET",
        f"{NOTIFICATION_SERVICE_URL}/me/notifications?{qs}",
        None,
        request_id,
        user_payload,
    )


async def get_my_unread_count(request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(
        cb_notification,
        "GET",
        f"{NOTIFICATION_SERVICE_URL}/me/notifications/unread-count",
        None,
        request_id,
        user_payload,
    )


async def mark_my_notification_read(notification_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(
        cb_notification,
        "POST",
        f"{NOTIFICATION_SERVICE_URL}/me/notifications/{notification_id}/read",
        None,
        request_id,
        user_payload,
    )


async def mark_all_my_notifications_read(request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(
        cb_notification,
        "POST",
        f"{NOTIFICATION_SERVICE_URL}/me/notifications/read-all",
        None,
        request_id,
        user_payload,
    )


async def archive_my_notification(notification_id: str, request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(
        cb_notification,
        "POST",
        f"{NOTIFICATION_SERVICE_URL}/me/notifications/{notification_id}/archive",
        None,
        request_id,
        user_payload,
    )


async def get_my_notification_preferences(request_id: str | None = None, user_payload: dict | None = None):
    return await _call_with_breaker(
        cb_notification,
        "GET",
        f"{NOTIFICATION_SERVICE_URL}/me/notification-preferences",
        None,
        request_id,
        user_payload,
    )


async def update_my_notification_preferences(
    data: dict,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await _call_with_breaker(
        cb_notification,
        "PUT",
        f"{NOTIFICATION_SERVICE_URL}/me/notification-preferences",
        data,
        request_id,
        user_payload,
    )


async def register_my_push_device(
    data: dict,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await _call_with_breaker(
        cb_notification,
        "POST",
        f"{NOTIFICATION_SERVICE_URL}/me/push-devices",
        data,
        request_id,
        user_payload,
    )


async def delete_my_push_device(
    device_id: int,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await _call_with_breaker(
        cb_notification,
        "DELETE",
        f"{NOTIFICATION_SERVICE_URL}/me/push-devices/{device_id}",
        None,
        request_id,
        user_payload,
    )