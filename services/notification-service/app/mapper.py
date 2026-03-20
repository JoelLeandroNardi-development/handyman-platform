from __future__ import annotations

from typing import Any


class NotificationIntent(dict):
    pass


def _intent(
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


def _booking_requested(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    handyman_email = data.get("handyman_email")
    if not handyman_email:
        return []
    return [
        _intent(
            event_id=event_id,
            user_email=handyman_email,
            type="job.requested",
            priority="normal",
            title="New booking request",
            body="A user requested a booking with you.",
            booking_id=booking_id,
            action_prefix="jobs",
            payload={
                "booking_id": booking_id,
                "desired_start": data.get("desired_start"),
                "user_email": data.get("user_email"),
            },
        )
    ]


def _slot_reserved(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    if not user_email:
        return []
    return [
        _intent(
            event_id=event_id,
            user_email=user_email,
            type="booking.reserved",
            priority="high",
            title="Time slot reserved",
            body="Your requested time slot is temporarily reserved.",
            booking_id=booking_id,
            action_prefix="bookings",
            payload={
                "booking_id": booking_id,
                "desired_start": data.get("desired_start"),
            },
        )
    ]


def _slot_confirmed(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    handyman_email = data.get("handyman_email")
    desired_start = data.get("desired_start")

    intents: list[NotificationIntent] = []
    if user_email:
        intents.append(
            _intent(
                event_id=event_id,
                user_email=user_email,
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
        )
    if handyman_email:
        intents.append(
            _intent(
                event_id=event_id,
                user_email=handyman_email,
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
        )
    return intents


def _slot_rejected(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    if not user_email:
        return []
    return [
        _intent(
            event_id=event_id,
            user_email=user_email,
            type="booking.rejected",
            priority="high",
            title="Time slot unavailable",
            body="That booking request could not be reserved.",
            booking_id=booking_id,
            action_prefix="bookings",
            payload={"booking_id": booking_id, "reason": data.get("reason")},
        )
    ]


def _slot_expired(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    if not user_email:
        return []
    return [
        _intent(
            event_id=event_id,
            user_email=user_email,
            type="booking.expired",
            priority="normal",
            title="Reservation expired",
            body="Your temporary reservation expired before confirmation.",
            booking_id=booking_id,
            action_prefix="bookings",
            payload={"booking_id": booking_id},
        )
    ]


def _booking_released(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    handyman_email = data.get("handyman_email")
    reason = data.get("reason")

    intents: list[NotificationIntent] = []
    if user_email:
        intents.append(
            _intent(
                event_id=event_id,
                user_email=user_email,
                type="booking.cancelled",
                priority="normal",
                title="Booking cancelled",
                body="Your booking reservation was released.",
                booking_id=booking_id,
                action_prefix="bookings",
                payload={"booking_id": booking_id, "reason": reason},
            )
        )
    if handyman_email:
        intents.append(
            _intent(
                event_id=event_id,
                user_email=handyman_email,
                type="job.released",
                priority="normal",
                title="Job released",
                body="A reservation associated with your schedule was released.",
                booking_id=booking_id,
                action_prefix="jobs",
                payload={"booking_id": booking_id, "reason": reason},
            )
        )
    return intents


def _booking_completed(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    handyman_email = data.get("handyman_email")
    desired_start = data.get("desired_start")

    intents: list[NotificationIntent] = []
    if user_email:
        intents.append(
            _intent(
                event_id=event_id,
                user_email=user_email,
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
        )
    if handyman_email:
        intents.append(
            _intent(
                event_id=event_id,
                user_email=handyman_email,
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
        )
    return intents


def _booking_rejected(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    reason = data.get("reason")
    if not user_email:
        return []
    return [
        _intent(
            event_id=event_id,
            user_email=user_email,
            type="booking.rejected_by_handyman",
            priority="high",
            title="Booking rejected",
            body="Your booking was rejected by the handyman.",
            booking_id=booking_id,
            action_prefix="bookings",
            payload={"booking_id": booking_id, "reason": reason},
        )
    ]


def _booking_completed_by_user(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    handyman_email = data.get("handyman_email")
    user_email = data.get("user_email")
    if not handyman_email:
        return []
    return [
        _intent(
            event_id=event_id,
            user_email=handyman_email,
            type="job.completion_requested",
            priority="high",
            title="Customer marked job as complete",
            body="The customer has marked this booking as complete. Please confirm your side to close it.",
            booking_id=booking_id,
            action_prefix="jobs",
            payload={"booking_id": booking_id, "user_email": user_email},
        )
    ]


def _booking_completed_by_handyman(event_id: str, data: dict[str, Any]) -> list[NotificationIntent]:
    booking_id = data.get("booking_id")
    user_email = data.get("user_email")
    handyman_email = data.get("handyman_email")
    if not user_email:
        return []
    return [
        _intent(
            event_id=event_id,
            user_email=user_email,
            type="booking.completion_requested",
            priority="high",
            title="Handyman marked job as complete",
            body="Your handyman has marked the job as complete. Please confirm your side to close the booking.",
            booking_id=booking_id,
            action_prefix="bookings",
            payload={"booking_id": booking_id, "handyman_email": handyman_email},
        )
    ]


EVENT_MAPPERS: dict[str, Any] = {
    "booking.requested": _booking_requested,
    "slot.reserved": _slot_reserved,
    "slot.confirmed": _slot_confirmed,
    "slot.rejected": _slot_rejected,
    "slot.expired": _slot_expired,
    "slot.released": _booking_released,
    "booking.cancel_requested": _booking_released,
    "booking.completed": _booking_completed,
    "booking.rejected": _booking_rejected,
    "booking.completed_by_user": _booking_completed_by_user,
    "booking.completed_by_handyman": _booking_completed_by_handyman,
}


def map_event_to_notifications(event: dict[str, Any]) -> list[NotificationIntent]:
    event_type = event.get("event_type")
    event_id = event.get("event_id")
    data = event.get("data") or {}

    if not event_type or not event_id:
        return []

    mapper = EVENT_MAPPERS.get(event_type)
    if mapper is None:
        return []
    return mapper(event_id, data)
