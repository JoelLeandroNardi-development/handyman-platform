from pydantic import BaseModel, Field
from typing import List, Optional


_ALLOWED_ROLES = {"user", "handyman", "admin"}


class Register(BaseModel):
    email: str
    password: str
    roles: List[str] = Field(default_factory=lambda: ["user"])

    def model_post_init(self, __context):
        normalized = []
        for r in self.roles:
            rr = r.strip().lower()
            if rr not in _ALLOWED_ROLES:
                raise ValueError(
                    f"Invalid role: {r}. Allowed: {sorted(_ALLOWED_ROLES)}"
                )
            if rr not in normalized:
                normalized.append(rr)

        if not normalized:
            normalized = ["user"]

        object.__setattr__(self, "roles", normalized)


class Login(BaseModel):
    email: str
    password: str


class AuthUserResponse(BaseModel):
    id: int
    email: str
    roles: List[str]


class UpdateAuthUserPassword(BaseModel):
    password: str = Field(..., min_length=6)


class UpdateAuthUserRoles(BaseModel):
    roles: List[str] = Field(default_factory=list)

    def model_post_init(self, __context):
        normalized = []
        for r in self.roles:
            rr = (r or "").strip().lower()
            if rr not in _ALLOWED_ROLES:
                raise ValueError(f"Invalid role: {r}. Allowed: {sorted(_ALLOWED_ROLES)}")
            if rr not in normalized:
                normalized.append(rr)
        if not normalized:
            raise ValueError("roles must not be empty")
        object.__setattr__(self, "roles", normalized)


class UpdateAuthUser(BaseModel):
    """
    Back-office update payload.
    For now you asked mainly for password; roles are included as optional
    because it's typically needed in admin UIs.
    """
    password: Optional[str] = Field(default=None, min_length=6)
    roles: Optional[List[str]] = None

    def model_post_init(self, __context):
        if self.roles is None:
            return

        normalized: list[str] = []
        for r in self.roles:
            rr = (r or "").strip().lower()
            if rr not in _ALLOWED_ROLES:
                raise ValueError(f"Invalid role: {r}. Allowed: {sorted(_ALLOWED_ROLES)}")
            if rr not in normalized:
                normalized.append(rr)

        if not normalized:
            raise ValueError("roles must not be empty")

        object.__setattr__(self, "roles", normalized)