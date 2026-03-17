from __future__ import annotations

import json

from fastapi import Header, HTTPException, status


async def get_current_email(x_user_email: str | None = Header(default=None)) -> str:
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header",
        )
    return x_user_email


async def get_current_roles(x_user_roles: str | None = Header(default=None)) -> list[str]:
    if not x_user_roles:
        return []
    try:
        parsed = json.loads(x_user_roles)
        if isinstance(parsed, list):
            return [str(role) for role in parsed]
    except Exception:
        pass
    return []
