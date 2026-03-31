from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from dateutil import parser

from ..domain.models import MatchLog
from ..domain.schemas import MatchLogResponse

def log_to_response(row: MatchLog) -> MatchLogResponse:
    return MatchLogResponse(
        id=row.id,
        user_latitude=row.user_latitude,
        user_longitude=row.user_longitude,
        skill=row.skill,
        job_description=row.job_description,
    )

def norm(s: str) -> str:
    return (s or "").strip().lower()

def safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default

def safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default

def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def parse_dt(x: Any) -> datetime:
    if isinstance(x, datetime):
        return as_utc(x)
    if isinstance(x, str):
        return as_utc(parser.isoparse(x))
    raise ValueError(f"Unsupported datetime type: {type(x).__name__}")

def normalize_handyman(doc: dict) -> dict:
    email = (doc or {}).get("email")
    if not email:
        return {}

    skills = doc.get("skills") or []
    skills_norm = [norm(s) for s in skills if s]
    seen = set()
    skills_norm = [s for s in skills_norm if not (s in seen or seen.add(s))]

    return {
        "email": email,
        "skills": skills_norm,
        "years_experience": doc.get("years_experience"),
        "service_radius_km": doc.get("service_radius_km"),
        "latitude": doc.get("latitude"),
        "longitude": doc.get("longitude"),
        "avg_rating": float(doc.get("avg_rating") or 0),
        "rating_count": int(doc.get("rating_count") or 0),
        "profile_completeness": int(doc.get("profile_completeness") or 0),
        "completed_jobs_count": int(doc.get("completed_jobs_count") or 0),
        "updated_at": utc_now_iso(),
    }