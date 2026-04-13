from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, JSON, func

from .constants import AuthProvider, ForeignKeyName, SERVER_DEFAULT_FALSE, TableName
from ..infrastructure.db import Base

class AuthUser(Base):
    __tablename__ = TableName.AUTH_USERS

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    roles = Column(JSON, nullable=False)
    is_email_verified = Column(Boolean, nullable=False, server_default=SERVER_DEFAULT_FALSE)
    auth_provider = Column(String(20), nullable=False, server_default=AuthProvider.LOCAL)
    google_sub = Column(String(255), nullable=True, unique=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

class AuthSession(Base):
    __tablename__ = TableName.AUTH_SESSIONS

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey(ForeignKeyName.AUTH_USERS_ID, ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(128), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)

class PasswordResetToken(Base):
    __tablename__ = TableName.PASSWORD_RESET_TOKENS

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey(ForeignKeyName.AUTH_USERS_ID, ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class EmailVerificationToken(Base):
    __tablename__ = TableName.EMAIL_VERIFICATION_TOKENS

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey(ForeignKeyName.AUTH_USERS_ID, ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())