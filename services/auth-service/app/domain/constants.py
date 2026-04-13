from __future__ import annotations
from enum import StrEnum

class TableName(StrEnum):
    AUTH_USERS = "auth_users"
    AUTH_SESSIONS = "auth_sessions"
    PASSWORD_RESET_TOKENS = "password_reset_tokens"
    EMAIL_VERIFICATION_TOKENS = "email_verification_tokens"

class ForeignKeyName(StrEnum):
    AUTH_USERS_ID = "auth_users.id"

class AuthProvider(StrEnum):
    LOCAL = "local"
    GOOGLE = "google"

class TokenClaim(StrEnum):
    SUBJECT = "sub"
    ROLES = "roles"
    ISSUED_AT = "iat"
    EXPIRES_AT = "exp"
    JWT_ID = "jti"
    SESSION_ID = "sid"
    TOKEN_TYPE = "typ"

class TokenType(StrEnum):
    REFRESH = "refresh"

class UserRole(StrEnum):
    USER = "user"

class GoogleIssuer(StrEnum):
    ACCOUNTS = "accounts.google.com"
    HTTPS_ACCOUNTS = "https://accounts.google.com"

class ErrorMessage(StrEnum):
    EMAIL_ALREADY_EXISTS = "Email already exists"
    USER_REGISTERED = "User registered"
    INVALID_CREDENTIALS = "Invalid credentials"
    INVALID_OR_EXPIRED_REFRESH_TOKEN = "Invalid or expired refresh token"
    INVALID_TOKEN_TYPE = "Invalid token type"
    MALFORMED_REFRESH_TOKEN = "Malformed refresh token"
    SESSION_NOT_FOUND = "Session not found"
    SESSION_REVOKED = "Session revoked"
    SESSION_EXPIRED = "Session expired"
    USER_NOT_FOUND = "User not found"
    GOOGLE_CLIENT_ID_NOT_CONFIGURED = "GOOGLE_CLIENT_ID is not configured"
    INVALID_GOOGLE_ID_TOKEN = "Invalid Google ID token"
    INVALID_GOOGLE_TOKEN_ISSUER = "Invalid Google token issuer"
    GOOGLE_TOKEN_MISSING_REQUIRED_CLAIMS = "Google token missing required claims"
    GOOGLE_ACCOUNT_EMAIL_NOT_VERIFIED = "Google account email is not verified"
    INVALID_RESET_TOKEN = "Invalid reset token"
    RESET_TOKEN_ALREADY_USED = "Reset token already used"
    RESET_TOKEN_EXPIRED = "Reset token expired"
    INVALID_VERIFICATION_TOKEN = "Invalid verification token"
    VERIFICATION_TOKEN_ALREADY_USED = "Verification token already used"
    VERIFICATION_TOKEN_EXPIRED = "Verification token expired"

class ResponseKey(StrEnum):
    MESSAGE = "message"
    ROLES = "roles"
    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"
    EXPIRES_IN = "expires_in"
    OK = "ok"
    IS_NEW_USER = "is_new_user"
    EMAIL = "email"

SERVER_DEFAULT_FALSE = "false"
DEBUG_TRUE_VALUES = frozenset({"1", "true", "yes"})