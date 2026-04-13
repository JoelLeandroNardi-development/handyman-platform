from __future__ import annotations

from ..domain.constants import PreferenceCategory
from ..domain.models import NotificationPreference

def category_enabled(pref: NotificationPreference, category: str) -> bool:
    if category == PreferenceCategory.BOOKING:
        return pref.booking_in_app_enabled
    if category == PreferenceCategory.CHAT:
        return pref.chat_in_app_enabled
    return pref.system_in_app_enabled