from __future__ import annotations

import re
from typing import Iterable


ROUTING_KEYS = [
    "booking.requested",
    "slot.reserved",
    "slot.confirmed",
    "slot.rejected",
    "slot.expired",
    "booking.cancel_requested",
]

CHANNELS_BY_EVENT = {
    "booking.requested": ["email", "push"],
    "slot.reserved": ["push"],
    "slot.confirmed": ["email", "push"],
    "slot.rejected": ["push"],
    "slot.expired": ["email", "push"],
    "booking.cancel_requested": ["email", "push"],
}


def channels_for_event(event_type: str) -> list[str]:
    return CHANNELS_BY_EVENT.get(event_type, [])


def extract_email_recipients(data: dict) -> list[str]:
    candidates = [
        data.get("user_email"),
        data.get("handyman_email"),
        data.get("email"),
    ]
    out: list[str] = []
    seen = set()
    for value in candidates:
        if not value or not isinstance(value, str):
            continue
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _sanitize_topic(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned


def extract_push_targets(data: dict) -> list[str]:
    candidates = [
        data.get("user_push_topic"),
        data.get("handyman_push_topic"),
        data.get("push_topic"),
    ]

    if not any(value for value in candidates if isinstance(value, str) and value.strip()):
        candidates.extend(
            [
                data.get("user_email"),
                data.get("handyman_email"),
                data.get("email"),
            ]
        )

    out: list[str] = []
    seen = set()
    for value in candidates:
        if not value or not isinstance(value, str):
            continue
        topic = _sanitize_topic(value)
        if not topic or topic in seen:
            continue
        seen.add(topic)
        out.append(topic)
    return out


def render_notification(event_type: str, data: dict) -> tuple[str, str]:
    booking_id = data.get("booking_id", "unknown")

    titles = {
        "booking.requested": "Booking request received",
        "slot.reserved": "Booking slot reserved",
        "slot.confirmed": "Booking confirmed",
        "slot.rejected": "Booking rejected",
        "slot.expired": "Booking reservation expired",
        "booking.cancel_requested": "Booking cancellation requested",
    }

    title = titles.get(event_type, "Booking update")

    reason = data.get("reason")
    if reason:
        body = f"Event {event_type} for booking {booking_id}. Reason: {reason}."
    else:
        body = f"Event {event_type} for booking {booking_id}."

    return title, body


def iter_notification_targets(channels: Iterable[str], recipients: Iterable[str]):
    for channel in channels:
        for recipient in recipients:
            yield channel, recipient
