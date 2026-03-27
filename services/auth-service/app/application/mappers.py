from ..domain.models import AuthUser
from ..domain.schemas import AuthUserResponse

def to_auth_user_response(u: AuthUser) -> AuthUserResponse:
    return AuthUserResponse(
        id=u.id,
        email=u.email,
        roles=list(u.roles or []),
        is_email_verified=bool(u.is_email_verified),
        auth_provider=str(u.auth_provider or "local"),
        google_sub=u.google_sub,
        last_login_at=u.last_login_at,
    )