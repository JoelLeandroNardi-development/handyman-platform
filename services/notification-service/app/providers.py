from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from email.message import EmailMessage
import os
import smtplib

import httpx


_RECENT = deque(maxlen=500)

SMTP_ENABLED = os.getenv("NOTIFY_EMAIL_ENABLED", "true").lower() == "true"
SMTP_HOST = os.getenv("SMTP_HOST", "mailhog")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@handyman.local")

PUSH_ENABLED = os.getenv("NOTIFY_PUSH_ENABLED", "true").lower() == "true"
NTFY_BASE_URL = os.getenv("NTFY_BASE_URL", "http://ntfy:80").rstrip("/")


def _record(
    channel: str,
    recipient: str,
    title: str,
    body: str,
    event_id: str,
    event_type: str,
    *,
    status: str,
    error: str | None = None,
):
    _RECENT.append(
        {
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "recipient": recipient,
            "status": status,
            "error": error,
            "title": title,
            "body": body,
            "event_id": event_id,
            "event_type": event_type,
        }
    )


def _send_email_sync(recipient: str, title: str, body: str):
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = recipient
    message["Subject"] = title
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USERNAME:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)


async def send_email(recipient: str, title: str, body: str, event_id: str, event_type: str):
    if not SMTP_ENABLED:
        _record("email", recipient, title, body, event_id, event_type, status="skipped", error="email_disabled")
        return

    try:
        await asyncio.to_thread(_send_email_sync, recipient, title, body)
        _record("email", recipient, title, body, event_id, event_type, status="sent")
        print(f"[notification-service] email -> {recipient} | {title}")
    except Exception as exc:
        _record("email", recipient, title, body, event_id, event_type, status="failed", error=str(exc))
        raise


async def send_push(recipient: str, title: str, body: str, event_id: str, event_type: str):
    if not PUSH_ENABLED:
        _record("push", recipient, title, body, event_id, event_type, status="skipped", error="push_disabled")
        return

    url = f"{NTFY_BASE_URL}/{recipient}"
    headers = {
        "Title": title,
        "Tags": "wrench,bell",
        "X-Event-Id": event_id,
        "X-Event-Type": event_type,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, content=body.encode("utf-8"), headers=headers)
            response.raise_for_status()
        _record("push", recipient, title, body, event_id, event_type, status="sent")
        print(f"[notification-service] push -> {recipient} | {title}")
    except Exception as exc:
        _record("push", recipient, title, body, event_id, event_type, status="failed", error=str(exc))
        raise


async def send_channel(channel: str, recipient: str, title: str, body: str, event_id: str, event_type: str):
    if channel == "email":
        await send_email(recipient, title, body, event_id, event_type)
        return
    if channel == "push":
        await send_push(recipient, title, body, event_id, event_type)
        return


def providers_config() -> dict:
    return {
        "email": {
            "enabled": SMTP_ENABLED,
            "smtp_host": SMTP_HOST,
            "smtp_port": SMTP_PORT,
            "smtp_use_tls": SMTP_USE_TLS,
            "smtp_from": SMTP_FROM,
        },
        "push": {
            "enabled": PUSH_ENABLED,
            "ntfy_base_url": NTFY_BASE_URL,
        },
    }


def recent_notifications(limit: int = 50) -> list[dict]:
    if limit <= 0:
        return []
    rows = list(_RECENT)
    return rows[-limit:]


def recent_count() -> int:
    return len(_RECENT)
