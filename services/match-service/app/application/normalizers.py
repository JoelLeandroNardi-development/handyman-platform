from shared.core.utils.datetime import utc_now_iso
from shared.core.utils.normalize import norm

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