from __future__ import annotations

from fastapi import Header, HTTPException, status


async def get_current_email(x_user_email: str | None = Header(default=None)) -> str:
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header",
        )
    return x_user_email
