from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt


JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM") or "HS256"
ACCESS_TOKEN_TTL_MIN = int(os.getenv("ACCESS_TOKEN_TTL_MIN", "15"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _encode_token(payload: dict) -> str:
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token_pair(*, user_email: str, roles: list[str], session_id: str) -> TokenPair:
    now = _now_utc()

    access_expires_at = now + timedelta(minutes=ACCESS_TOKEN_TTL_MIN)
    refresh_expires_at = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

    access_payload = {
        "sub": user_email,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int(access_expires_at.timestamp()),
        "jti": str(uuid4()),
        "sid": session_id,
    }

    refresh_payload = {
        "sub": user_email,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int(refresh_expires_at.timestamp()),
        "jti": str(uuid4()),
        "sid": session_id,
        "typ": "refresh",
    }

    return TokenPair(
        access_token=_encode_token(access_payload),
        refresh_token=_encode_token(refresh_payload),
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )


__all__ = [
    "JWTError",
    "TokenPair",
    "decode_token",
    "hash_token",
    "issue_token_pair",
]
