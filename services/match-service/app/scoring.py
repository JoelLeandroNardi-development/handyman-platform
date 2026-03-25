"""Scoring module – ranking weights, datetime helpers, and scoring functions for /match candidates."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from dateutil import parser

# B5 ranking weights: distance remains dominant, trust signals provide meaningful lift.
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


def norm(s: str) -> str:
    return (s or "").strip().lower()


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_dt(x: Any) -> datetime:
    if isinstance(x, datetime):
        return _as_utc(x)
    if isinstance(x, str):
        return _as_utc(parser.isoparse(x))
    raise ValueError(f"Unsupported datetime type: {type(x).__name__}")


def _distance_score(distance_km: Any) -> float:
    km = max(0.0, _safe_float(distance_km, default=1_000_000.0))
    return 1.0 / (1.0 + (km / 10.0))


def _dampened_count_score(value: Any, *, cap: int) -> float:
    cap = max(1, int(cap))
    count = max(0, _safe_int(value, default=0))
    return _clamp01(math.log1p(count) / math.log1p(cap))


def compute_match_score(candidate: dict[str, Any]) -> float:
    """Compute deterministic weighted ranking score for /match candidates."""
    avg_rating = _clamp01(_safe_float(candidate.get("avg_rating"), default=0.0) / 5.0)
    availability_confidence = 0.0 if bool(candidate.get("availability_unknown")) else 1.0
    profile_completeness = _clamp01(_safe_float(candidate.get("profile_completeness"), default=0.0) / 100.0)

    score = 0.0
    score += RANKING_WEIGHTS["distance"] * _distance_score(candidate.get("distance_km"))
    score += RANKING_WEIGHTS["avg_rating"] * avg_rating
    score += RANKING_WEIGHTS["availability_confidence"] * availability_confidence
    score += RANKING_WEIGHTS["profile_completeness"] * profile_completeness
    score += RANKING_WEIGHTS["rating_count"] * _dampened_count_score(
        candidate.get("rating_count"),
        cap=RANKING_CAPS["rating_count"],
    )
    score += RANKING_WEIGHTS["completed_jobs_count"] * _dampened_count_score(
        candidate.get("completed_jobs_count"),
        cap=RANKING_CAPS["completed_jobs_count"],
    )
    years = _safe_float(candidate.get("years_experience"), default=0.0)
    score += RANKING_WEIGHTS["years_experience"] * _clamp01(years / float(RANKING_CAPS["years_experience"]))
    return score


def rank_match_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by score desc, then deterministic tie-breakers."""

    def sort_key(c: dict[str, Any]) -> tuple[float, float, int, str]:
        score = compute_match_score(c)
        distance = max(0.0, _safe_float(c.get("distance_km"), default=1_000_000.0))
        rating_count = max(0, _safe_int(c.get("rating_count"), default=0))
        email = str(c.get("email") or "")
        return (-score, distance, -rating_count, email)

    return sorted(candidates, key=sort_key)
