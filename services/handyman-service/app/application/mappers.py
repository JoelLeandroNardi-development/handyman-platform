from ..domain.profile_policies import compute_profile_completeness
from ..domain.models import Handyman, HandymanReview
from ..domain.schemas import HandymanResponse, HandymanReviewResponse

def _completeness(h) -> int:
    return compute_profile_completeness(
        first_name=h.first_name,
        last_name=h.last_name,
        phone=h.phone,
        city=h.city,
        country=h.country,
        skills=h.skills,
        years_experience=h.years_experience,
        service_radius_km=h.service_radius_km,
        latitude=h.latitude,
        longitude=h.longitude,
    )

def _to_response(h: Handyman) -> HandymanResponse:
    return HandymanResponse(
        email=h.email,
        first_name=h.first_name,
        last_name=h.last_name,
        phone=h.phone,
        national_id=h.national_id,
        address_line=h.address_line,
        postal_code=h.postal_code,
        city=h.city,
        country=h.country,
        skills=list(h.skills or []),
        years_experience=h.years_experience,
        service_radius_km=h.service_radius_km,
        latitude=h.latitude,
        longitude=h.longitude,
        avg_rating=float(h.avg_rating or 0),
        rating_count=int(h.rating_count or 0),
        profile_completeness=_completeness(h),
        created_at=h.created_at,
    )

def _handyman_event_data(h) -> dict:
    return {
        "email": h.email,
        "first_name": h.first_name,
        "last_name": h.last_name,
        "phone": h.phone,
        "national_id": h.national_id,
        "address_line": h.address_line,
        "postal_code": h.postal_code,
        "city": h.city,
        "country": h.country,
        "skills": list(h.skills or []),
        "years_experience": h.years_experience,
        "service_radius_km": h.service_radius_km,
        "latitude": h.latitude,
        "longitude": h.longitude,
        "avg_rating": float(h.avg_rating or 0),
        "rating_count": int(h.rating_count or 0),
        "profile_completeness": _completeness(h),
    }

def _review_to_response(r: HandymanReview) -> HandymanReviewResponse:
    return HandymanReviewResponse(
        id=r.id,
        booking_id=r.booking_id,
        handyman_email=r.handyman_email,
        user_email=r.user_email,
        rating=r.rating,
        review_text=r.review_text,
        created_at=r.created_at,
    )