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


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class EmailVerifyRequest(BaseModel):
    email: str


class EmailVerifyConfirmRequest(BaseModel):
    token: str


class AuthActionResponse(BaseModel):
    ok: bool = True
    # Useful while SMTP is not wired; frontend can ignore this field.
    debug_token: str | None = None


class AuthUserResponse(BaseModel):
    id: int
    email: str
    roles: List[str]
    is_email_verified: bool = False
    auth_provider: str = "local"
    google_sub: str | None = None
    last_login_at: datetime | None = None


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
