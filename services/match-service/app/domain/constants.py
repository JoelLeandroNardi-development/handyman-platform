from __future__ import annotations
from enum import StrEnum

class MatchEventType(StrEnum):
    AVAILABILITY_UPDATED = "availability.updated"
    HANDYMAN_CREATED = "handyman.created"
    HANDYMAN_LOCATION_UPDATED = "handyman.location_updated"
    HANDYMAN_UPDATED = "handyman.updated"
    HANDYMAN_DELETED = "handyman.deleted"

class CacheMode(StrEnum):
    STRICT = "strict"
    DEGRADED = "degraded"

class ProjectionSource(StrEnum):
    PROJECTION = "projection"
    LIVE = "live"
    MISSING = "missing"
    EMPTY_SKILL = "empty-skill"

class SeedReason(StrEnum):
    ALREADY_PRESENT = "already_present"
    BOOTSTRAPPED = "bootstrapped"

class TableName(StrEnum):
    MATCH_LOGS = "match_logs"

RANKING_WEIGHTS = {
    "distance": 0.42,
    "avg_rating": 0.24,
    "availability_confidence": 0.12,
    "profile_completeness": 0.10,
    "rating_count": 0.06,
    "completed_jobs_count": 0.05,
    "years_experience": 0.01,
}

RANKING_CAPS = {
    "rating_count": 50,
    "completed_jobs_count": 100,
    "years_experience": 30,
}