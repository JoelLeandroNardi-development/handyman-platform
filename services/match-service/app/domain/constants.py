import os

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

GRID_DEG = float(os.getenv("MATCH_GRID_DEG") or "0.05")
TIME_BUCKET_SECONDS = int(os.getenv("MATCH_TIME_BUCKET_SECONDS") or "900")