from __future__ import annotations

from ..domain.constants import PREFERENCE_CATEGORY_BOOKING, PREFERENCE_CATEGORY_CHAT
from ..domain.models import NotificationPreference

def category_enabled(pref: NotificationPreference, category: str) -> bool:
    if category == PREFERENCE_CATEGORY_BOOKING:
        return pref.booking_in_app_enabled
    if category == PREFERENCE_CATEGORY_CHAT:
        return pref.chat_in_app_enabled
    return pref.system_in_app_enabled