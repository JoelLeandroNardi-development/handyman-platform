from app.domain.models import User
from app.domain.schemas import UserResponse

def _to_response(u: User) -> UserResponse:
    return UserResponse(
        email=u.email,
        first_name=u.first_name,
        last_name=u.last_name,
        phone=u.phone,
        national_id=u.national_id,
        address_line=u.address_line,
        postal_code=u.postal_code,
        city=u.city,
        country=u.country,
        latitude=u.latitude,
        longitude=u.longitude,
        created_at=u.created_at,
    )