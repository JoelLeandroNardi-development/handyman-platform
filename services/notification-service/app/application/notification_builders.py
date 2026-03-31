from __future__ import annotations

from typing import Any

from ..domain.notification_types import NotificationIntent

def booking_intent(
    *,
    event_id: str,
    user_email: str,
    type: str,
    priority: str,
    title: str,
    body: str,
    booking_id: str | None,
    action_prefix: str,
    payload: dict[str, Any],
) -> NotificationIntent:
    return NotificationIntent(
        user_email=user_email,
        event_id=event_id,
        type=type,
        category="booking",
        priority=priority,
        title=title,
        body=body,
        entity_type="booking",
        entity_id=booking_id,
        action_url=f"/{action_prefix}/{booking_id}" if booking_id else None,
        payload=payload,
    )

def single_booking_notification(
    *,
    event_id: str,
    recipient_email: str | None,
    type: str,
    priority: str,
    title: str,
    body: str,
    booking_id: str | None,
    action_prefix: str,
    payload: dict[str, Any],
) -> list[NotificationIntent]:
    if not recipient_email:
        return []

    return [
        booking_intent(
            event_id=event_id,
            user_email=recipient_email,
            type=type,
            priority=priority,
            title=title,
            body=body,
            booking_id=booking_id,
            action_prefix=action_prefix,
            payload=payload,
        )
    ]

def append_booking_notification(
    intents: list[NotificationIntent],
    *,
    recipient_email: str | None,
    event_id: str,
    type: str,
    priority: str,
    title: str,
    body: str,
    booking_id: str | None,
    action_prefix: str,
    payload: dict[str, Any],
) -> None:
    if not recipient_email:
        return

    intents.append(
        booking_intent(
            event_id=event_id,
            user_email=recipient_email,
            type=type,
            priority=priority,
            title=title,
            body=body,
            booking_id=booking_id,
            action_prefix=action_prefix,
            payload=payload,
        )
    )

def pick_payload(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: data.get(key) for key in keys}