from __future__ import annotations

from typing import Any, Callable

from .notification_builders import append_booking_notification, pick_payload, single_booking_notification
from ..domain.constants import (
    ActionPrefix, NotificationBody, DataKey, EventType,
    NotificationPriority, NotificationType, NotificationTitle,
)
from ..domain.notification_types import NotificationIntent

def booking_requested(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get(DataKey.HANDYMAN_EMAIL),
        type=NotificationType.JOB_REQUESTED,
        priority=NotificationPriority.NORMAL,
        title=NotificationTitle.NEW_BOOKING_REQUEST,
        body=NotificationBody.USER_REQUESTED_BOOKING,
        booking_id=booking_id,
        action_prefix=ActionPrefix.JOBS,
        payload=pick_payload(data, DataKey.BOOKING_ID, DataKey.DESIRED_START, DataKey.USER_EMAIL),
    )

def slot_reserved(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get(DataKey.USER_EMAIL),
        type=NotificationType.BOOKING_RESERVED,
        priority=NotificationPriority.HIGH,
        title=NotificationTitle.TIME_SLOT_RESERVED,
        body=NotificationBody.SLOT_TEMP_RESERVED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.BOOKINGS,
        payload=pick_payload(data, DataKey.BOOKING_ID, DataKey.DESIRED_START),
    )

def slot_confirmed(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    user_email = data.get(DataKey.USER_EMAIL)
    handyman_email = data.get(DataKey.HANDYMAN_EMAIL)
    desired_start = data.get(DataKey.DESIRED_START)

    intents: list[NotificationIntent] = []

    append_booking_notification(
        intents,
        recipient_email=user_email,
        event_id=event_id,
        type=NotificationType.BOOKING_CONFIRMED,
        priority=NotificationPriority.HIGH,
        title=NotificationTitle.BOOKING_CONFIRMED,
        body=NotificationBody.BOOKING_CONFIRMED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.BOOKINGS,
        payload={
            DataKey.BOOKING_ID: booking_id,
            DataKey.DESIRED_START: desired_start,
            DataKey.HANDYMAN_EMAIL: handyman_email,
        },
    )

    append_booking_notification(
        intents,
        recipient_email=handyman_email,
        event_id=event_id,
        type=NotificationType.JOB_CONFIRMED,
        priority=NotificationPriority.HIGH,
        title=NotificationTitle.NEW_CONFIRMED_JOB,
        body=NotificationBody.JOB_CONFIRMED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.JOBS,
        payload={
            DataKey.BOOKING_ID: booking_id,
            DataKey.DESIRED_START: desired_start,
            DataKey.USER_EMAIL: user_email,
        },
    )

    return intents

def slot_rejected(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get(DataKey.USER_EMAIL),
        type=NotificationType.BOOKING_REJECTED,
        priority=NotificationPriority.HIGH,
        title=NotificationTitle.TIME_SLOT_UNAVAILABLE,
        body=NotificationBody.BOOKING_NOT_RESERVED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.BOOKINGS,
        payload=pick_payload(data, DataKey.BOOKING_ID, DataKey.REASON),
    )

def slot_expired(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get(DataKey.USER_EMAIL),
        type=NotificationType.BOOKING_EXPIRED,
        priority=NotificationPriority.NORMAL,
        title=NotificationTitle.RESERVATION_EXPIRED,
        body=NotificationBody.RESERVATION_EXPIRED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.BOOKINGS,
        payload=pick_payload(data, DataKey.BOOKING_ID),
    )

def booking_released(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    user_email = data.get(DataKey.USER_EMAIL)
    handyman_email = data.get(DataKey.HANDYMAN_EMAIL)
    reason = data.get(DataKey.REASON)

    intents: list[NotificationIntent] = []

    append_booking_notification(
        intents,
        recipient_email=user_email,
        event_id=event_id,
        type=NotificationType.BOOKING_CANCELLED,
        priority=NotificationPriority.NORMAL,
        title=NotificationTitle.BOOKING_CANCELLED,
        body=NotificationBody.BOOKING_RELEASED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.BOOKINGS,
        payload={DataKey.BOOKING_ID: booking_id, DataKey.REASON: reason},
    )

    append_booking_notification(
        intents,
        recipient_email=handyman_email,
        event_id=event_id,
        type=NotificationType.JOB_RELEASED,
        priority=NotificationPriority.NORMAL,
        title=NotificationTitle.JOB_RELEASED,
        body=NotificationBody.JOB_RELEASED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.JOBS,
        payload={DataKey.BOOKING_ID: booking_id, DataKey.REASON: reason},
    )

    return intents

def booking_completed(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    user_email = data.get(DataKey.USER_EMAIL)
    handyman_email = data.get(DataKey.HANDYMAN_EMAIL)
    desired_start = data.get(DataKey.DESIRED_START)

    intents: list[NotificationIntent] = []

    append_booking_notification(
        intents,
        recipient_email=user_email,
        event_id=event_id,
        type=NotificationType.BOOKING_COMPLETED,
        priority=NotificationPriority.NORMAL,
        title=NotificationTitle.BOOKING_COMPLETED,
        body=NotificationBody.BOOKING_COMPLETED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.BOOKINGS,
        payload={
            DataKey.BOOKING_ID: booking_id,
            DataKey.DESIRED_START: desired_start,
            DataKey.HANDYMAN_EMAIL: handyman_email,
        },
    )

    append_booking_notification(
        intents,
        recipient_email=handyman_email,
        event_id=event_id,
        type=NotificationType.JOB_COMPLETED,
        priority=NotificationPriority.NORMAL,
        title=NotificationTitle.JOB_COMPLETED,
        body=NotificationBody.JOB_COMPLETED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.JOBS,
        payload={
            DataKey.BOOKING_ID: booking_id,
            DataKey.DESIRED_START: desired_start,
            DataKey.USER_EMAIL: user_email,
        },
    )

    return intents

def booking_rejected(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get(DataKey.USER_EMAIL),
        type=NotificationType.BOOKING_REJECTED_BY_HANDYMAN,
        priority=NotificationPriority.HIGH,
        title=NotificationTitle.BOOKING_REJECTED,
        body=NotificationBody.BOOKING_REJECTED,
        booking_id=booking_id,
        action_prefix=ActionPrefix.BOOKINGS,
        payload=pick_payload(data, DataKey.BOOKING_ID, DataKey.REASON),
    )

def booking_completed_by_user(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get(DataKey.HANDYMAN_EMAIL),
        type=NotificationType.JOB_COMPLETION_REQUESTED,
        priority=NotificationPriority.HIGH,
        title=NotificationTitle.CUSTOMER_MARKED_JOB_COMPLETE,
        body=NotificationBody.CUSTOMER_MARKED_JOB_COMPLETE,
        booking_id=booking_id,
        action_prefix=ActionPrefix.JOBS,
        payload=pick_payload(data, DataKey.BOOKING_ID, DataKey.USER_EMAIL),
    )

def booking_completed_by_handyman(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get(DataKey.BOOKING_ID)
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get(DataKey.USER_EMAIL),
        type=NotificationType.BOOKING_COMPLETION_REQUESTED,
        priority=NotificationPriority.HIGH,
        title=NotificationTitle.HANDYMAN_MARKED_JOB_COMPLETE,
        body=NotificationBody.HANDYMAN_MARKED_JOB_COMPLETE,
        booking_id=booking_id,
        action_prefix=ActionPrefix.BOOKINGS,
        payload=pick_payload(data, DataKey.BOOKING_ID, DataKey.HANDYMAN_EMAIL),
    )

EventMapper = Callable[[str, dict[str, Any]], list[NotificationIntent]]

EVENT_MAPPERS: dict[str, EventMapper] = {
    EventType.BOOKING_REQUESTED: booking_requested,
    EventType.SLOT_RESERVED: slot_reserved,
    EventType.SLOT_CONFIRMED: slot_confirmed,
    EventType.SLOT_REJECTED: slot_rejected,
    EventType.SLOT_EXPIRED: slot_expired,
    EventType.SLOT_RELEASED: booking_released,
    EventType.BOOKING_CANCEL_REQUESTED: booking_released,
    EventType.BOOKING_COMPLETED: booking_completed,
    EventType.BOOKING_REJECTED: booking_rejected,
    EventType.BOOKING_COMPLETED_BY_USER: booking_completed_by_user,
    EventType.BOOKING_COMPLETED_BY_HANDYMAN: booking_completed_by_handyman,
}