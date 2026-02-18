from pydantic import BaseModel, Field
from typing import List


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
