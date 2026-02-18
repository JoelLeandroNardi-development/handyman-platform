from fastapi import HTTPException, status


def require_role(payload: dict, allowed_roles: list[str]):
    token_roles = payload.get("roles")

    if not isinstance(token_roles, list) or not token_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Roles missing in token",
        )

    allowed = {r.lower() for r in allowed_roles}
    roles = {r.lower() for r in token_roles}

    if roles.isdisjoint(allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden for this role",
        )
