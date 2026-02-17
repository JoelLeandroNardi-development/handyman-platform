import math

def wilson_score(rating, n):
    if n == 0:
        return 0
    z = 1.96
    phat = rating / 5
    return (phat + z*z/(2*n) - z * math.sqrt((phat*(1-phat)+z*z/(4*n))/n)) / (1+z*z/n)

def score(distance_km, skill_overlap, rating, jobs_completed, available):
    geo_score = max(0, 1 - (distance_km / 50))
    skill_score = skill_overlap
    rating_score = wilson_score(rating, jobs_completed)
    availability_score = 1 if available else 0

    return (
        geo_score * 0.4 +
        skill_score * 0.3 +
        rating_score * 0.2 +
        availability_score * 0.1
    )
