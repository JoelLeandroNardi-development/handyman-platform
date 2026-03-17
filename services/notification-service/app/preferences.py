from __future__ import annotations

from .models import NotificationPreference


def category_enabled(pref: NotificationPreference, category: str) -> bool:
    if category == "booking":
        return pref.booking_in_app_enabled
    if category == "chat":
        return pref.chat_in_app_enabled
    return pref.system_in_app_enabled
