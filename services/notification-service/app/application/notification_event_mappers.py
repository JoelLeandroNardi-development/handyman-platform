from __future__ import annotations

from typing import Any, Callable

from .notification_builders import (
    append_booking_notification,
    pick_payload,
    single_booking_notification,
)
from ..domain.notification_types import NotificationIntent

def booking_requested(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get("handyman_email"),
        type="job.requested",
        priority="normal",
        title="New booking request",
        body="A user requested a booking with you.",
        booking_id=booking_id,
        action_prefix="jobs",
        payload=pick_payload(data, "booking_id", "desired_start", "user_email"),
    )

def slot_reserved(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get("user_email"),
        type="booking.reserved",
        priority="high",
        title="Time slot reserved",
        body="Your requested time slot is temporarily reserved.",
        booking_id=booking_id,
        action_prefix="bookings",
        payload=pick_payload(data, "booking_id", "desired_start"),
    )

def slot_confirmed(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    handyman_email = data.get("handyman_email")
    desired_start = data.get("desired_start")

    intents: list[NotificationIntent] = []

    append_booking_notification(
        intents,
        recipient_email=user_email,
        event_id=event_id,
        type="booking.confirmed",
        priority="high",
        title="Booking confirmed",
        body="Your booking has been confirmed.",
        booking_id=booking_id,
        action_prefix="bookings",
        payload={
            "booking_id": booking_id,
            "desired_start": desired_start,
            "handyman_email": handyman_email,
        },
    )

    append_booking_notification(
        intents,
        recipient_email=handyman_email,
        event_id=event_id,
        type="job.confirmed",
        priority="high",
        title="New confirmed job",
        body="A booking has been confirmed for you.",
        booking_id=booking_id,
        action_prefix="jobs",
        payload={
            "booking_id": booking_id,
            "desired_start": desired_start,
            "user_email": user_email,
        },
    )

    return intents

def slot_rejected(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get("user_email"),
        type="booking.rejected",
        priority="high",
        title="Time slot unavailable",
        body="That booking request could not be reserved.",
        booking_id=booking_id,
        action_prefix="bookings",
        payload=pick_payload(data, "booking_id", "reason"),
    )

def slot_expired(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get("user_email"),
        type="booking.expired",
        priority="normal",
        title="Reservation expired",
        body="Your temporary reservation expired before confirmation.",
        booking_id=booking_id,
        action_prefix="bookings",
        payload=pick_payload(data, "booking_id"),
    )

def booking_released(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    handyman_email = data.get("handyman_email")
    reason = data.get("reason")

    intents: list[NotificationIntent] = []

    append_booking_notification(
        intents,
        recipient_email=user_email,
        event_id=event_id,
        type="booking.cancelled",
        priority="normal",
        title="Booking cancelled",
        body="Your booking reservation was released.",
        booking_id=booking_id,
        action_prefix="bookings",
        payload={"booking_id": booking_id, "reason": reason},
    )

    append_booking_notification(
        intents,
        recipient_email=handyman_email,
        event_id=event_id,
        type="job.released",
        priority="normal",
        title="Job released",
        body="A reservation associated with your schedule was released.",
        booking_id=booking_id,
        action_prefix="jobs",
        payload={"booking_id": booking_id, "reason": reason},
    )

    return intents

def booking_completed(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    handyman_email = data.get("handyman_email")
    desired_start = data.get("desired_start")

    intents: list[NotificationIntent] = []

    append_booking_notification(
        intents,
        recipient_email=user_email,
        event_id=event_id,
        type="booking.completed",
        priority="normal",
        title="Booking completed",
        body="Your booking has been marked as completed.",
        booking_id=booking_id,
        action_prefix="bookings",
        payload={
            "booking_id": booking_id,
            "desired_start": desired_start,
            "handyman_email": handyman_email,
        },
    )

    append_booking_notification(
        intents,
        recipient_email=handyman_email,
        event_id=event_id,
        type="job.completed",
        priority="normal",
        title="Job completed",
        body="A job has been marked as completed.",
        booking_id=booking_id,
        action_prefix="jobs",
        payload={
            "booking_id": booking_id,
            "desired_start": desired_start,
            "user_email": user_email,
        },
    )

    return intents

def booking_rejected(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get("user_email"),
        type="booking.rejected_by_handyman",
        priority="high",
        title="Booking rejected",
        body="Your booking was rejected by the handyman.",
        booking_id=booking_id,
        action_prefix="bookings",
        payload=pick_payload(data, "booking_id", "reason"),
    )

def booking_completed_by_user(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get("handyman_email"),
        type="job.completion_requested",
        priority="high",
        title="Customer marked job as complete",
        body="The customer has marked this booking as complete. Please confirm your side to close it.",
        booking_id=booking_id,
        action_prefix="jobs",
        payload=pick_payload(data, "booking_id", "user_email"),
    )

def booking_completed_by_handyman(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    return single_booking_notification(
        event_id=event_id,
        recipient_email=data.get("user_email"),
        type="booking.completion_requested",
        priority="high",
        title="Handyman marked job as complete",
        body="Your handyman has marked the job as complete. Please confirm your side to close the booking.",
        booking_id=booking_id,
        action_prefix="bookings",
        payload=pick_payload(data, "booking_id", "handyman_email"),
    )

EventMapper = Callable[[str, dict[str, Any]], list[NotificationIntent]]

EVENT_MAPPERS: dict[str, EventMapper] = {
    "booking.requested": booking_requested,
    "slot.reserved": slot_reserved,
    "slot.confirmed": slot_confirmed,
    "slot.rejected": slot_rejected,
    "slot.expired": slot_expired,
    "slot.released": booking_released,
    "booking.cancel_requested": booking_released,
    "booking.completed": booking_completed,
    "booking.rejected": booking_rejected,
    "booking.completed_by_user": booking_completed_by_user,
    "booking.completed_by_handyman": booking_completed_by_handyman,
}