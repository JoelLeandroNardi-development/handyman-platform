from __future__ import annotations

import math
from typing import Any

from .constants import RANKING_WEIGHTS, RANKING_CAPS
from ..application.mappers import clamp01, safe_float, safe_int

def _distance_score(distance_km: Any) -> float:
    km = max(0.0, safe_float(distance_km, default=1_000_000.0))
    return 1.0 / (1.0 + (km / 10.0))

def _dampened_count_score(value: Any, *, cap: int) -> float:
    cap = max(1, int(cap))
    count = max(0, safe_int(value, default=0))
    return clamp01(math.log1p(count) / math.log1p(cap))

def compute_match_score(candidate: dict[str, Any]) -> float:
    avg_rating = clamp01(safe_float(candidate.get("avg_rating"), default=0.0) / 5.0)
    availability_confidence = 0.0 if bool(candidate.get("availability_unknown")) else 1.0
    profile_completeness = clamp01(safe_float(candidate.get("profile_completeness"), default=0.0) / 100.0)

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
    years = safe_float(candidate.get("years_experience"), default=0.0)
    score += RANKING_WEIGHTS["years_experience"] * clamp01(years / float(RANKING_CAPS["years_experience"]))
    return score

def rank_match_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(c: dict[str, Any]) -> tuple[float, float, int, str]:
        score = compute_match_score(c)
        distance = max(0.0, safe_float(c.get("distance_km"), default=1_000_000.0))
        rating_count = max(0, safe_int(c.get("rating_count"), default=0))
        email = str(c.get("email") or "")
        return (-score, distance, -rating_count, email)

    return sorted(candidates, key=sort_key)