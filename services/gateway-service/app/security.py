import os
from jose import jwt, JWTError
from fastapi import Request, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM") or "HS256"

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")

bearer_scheme = HTTPBearer(auto_error=False)


def _decode_and_bind(token: str, request: Request) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    request.state.user_sub = payload.get("sub")
    request.state.user_roles = payload.get("roles")
    return payload


def _extract_bearer_token(
    creds: HTTPAuthorizationCredentials | None,
) -> str | None:
    if creds and creds.scheme.lower() == "bearer":
        return creds.credentials
    return None


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    token = _extract_bearer_token(creds)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )

    return _decode_and_bind(token, request)


def get_current_user_sse(
    request: Request,
    access_token: str | None = Query(default=None),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    token = access_token or _extract_bearer_token(creds)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
        )

    return _decode_and_bind(token, request)