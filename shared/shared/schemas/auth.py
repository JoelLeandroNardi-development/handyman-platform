from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from shared.shared.roles import normalize_roles


class Register(BaseModel):
    email: str
    password: str
    roles: List[str] = Field(default_factory=lambda: ["user"])

    def model_post_init(self, __context):
        object.__setattr__(
            self, "roles", normalize_roles(self.roles, default=["user"])
        )


class Login(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str


class AuthUserResponse(BaseModel):
    id: int
    email: str
    roles: List[str]


class UpdateAuthUserPassword(BaseModel):
    password: str = Field(..., min_length=6)


class UpdateAuthUserRoles(BaseModel):
    roles: List[str] = Field(default_factory=list)

    def model_post_init(self, __context):
        object.__setattr__(self, "roles", normalize_roles(self.roles))


class UpdateAuthUser(BaseModel):

    password: Optional[str] = Field(default=None, min_length=6)
    roles: Optional[List[str]] = None

    def model_post_init(self, __context):
        if self.roles is None:
            return
        object.__setattr__(self, "roles", normalize_roles(self.roles))
