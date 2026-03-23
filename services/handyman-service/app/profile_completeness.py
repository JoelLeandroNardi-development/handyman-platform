"""Centralized profile-completeness computation for handyman profiles.

Score is a deterministic 0..100 integer based on eight profile-field checks.
Each check is equally weighted (12.5 points).  The result is rounded to the
nearest integer so that a fully-filled profile scores exactly 100.

Scoring inputs (from the spec):
  1. first_name         – truthy string
  2. last_name          – truthy string
  3. phone              – truthy string
  4. city or country    – at least one truthy string
  5. at least one skill – non-empty skills list
  6. years_experience   – positive value
  7. service_radius_km  – positive value
  8. latitude/longitude – both present (not None)
"""

from __future__ import annotations

from typing import Any, Sequence

_TOTAL_CHECKS = 8


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
    """Return a 0..100 integer representing how complete a handyman profile is."""
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
    return round(filled / _TOTAL_CHECKS * 100)
