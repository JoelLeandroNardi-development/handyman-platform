from __future__ import annotations

from typing import Any, Sequence

from .constants import PROFILE_COMPLETENESS_TOTAL_CHECKS

def compute_profile_completeness(
    *,
    first_name: Any = None,
    last_name: Any = None,
    phone: Any = None,
    city: Any = None,
    country: Any = None,
    skills: Sequence | None = None,
    years_experience: int | None = None,
    service_radius_km: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> int:
    filled = sum([
        bool(first_name),
        bool(last_name),
        bool(phone),
        bool(city) or bool(country),
        bool(skills),
        (years_experience or 0) > 0,
        (service_radius_km or 0) > 0,
        latitude is not None and longitude is not None,
    ])
    return round(filled / PROFILE_COMPLETENESS_TOTAL_CHECKS * 100)