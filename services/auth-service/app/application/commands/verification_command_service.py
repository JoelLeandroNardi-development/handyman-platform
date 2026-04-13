from uuid import uuid4
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.constants import DEBUG_TRUE_VALUES, ErrorMessage
from ...domain.models import AuthUser, PasswordResetToken,  EmailVerificationToken
from ...domain.schemas import ResetPasswordRequest, EmailVerifyRequest, EmailVerifyConfirmRequest, AuthActionResponse
from ...infrastructure.config import DEBUG_MODE
from ...infrastructure.password_hasher import password_hasher
from ...infrastructure.token_service import generate_opaque_token, hash_token

_DEBUG = DEBUG_MODE.lower() in DEBUG_TRUE_VALUES

class VerificationCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def forgot_password(self, email: str) -> AuthActionResponse:
        user_result = await self.db.execute(select(AuthUser).where(AuthUser.email == email))
        user = user_result.scalar_one_or_none()

        if not user:
            return AuthActionResponse(ok=True)

        raw_token = generate_opaque_token()
        reset = PasswordResetToken(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        self.db.add(reset)
        await self.db.commit()

        return AuthActionResponse(ok=True, debug_token=raw_token if _DEBUG else None)
    
    async def reset_password(self, data: ResetPasswordRequest) -> AuthActionResponse:
        token_hash = hash_token(data.token)
        token_result = await self.db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
        token_row = token_result.scalar_one_or_none()

        if not token_row:
            raise HTTPException(status_code=400, detail=ErrorMessage.INVALID_RESET_TOKEN)
        if token_row.used_at is not None:
            raise HTTPException(status_code=400, detail=ErrorMessage.RESET_TOKEN_ALREADY_USED)
        if token_row.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail=ErrorMessage.RESET_TOKEN_EXPIRED)

        user = await self.db.get(AuthUser, token_row.user_id)
        if not user:
            raise HTTPException(status_code=400, detail=ErrorMessage.USER_NOT_FOUND)

        user.password = password_hasher.hash(data.new_password)
        token_row.used_at = datetime.now(timezone.utc)
        await self.db.commit()

        return AuthActionResponse(ok=True)
    
    async def request_email_verification(self, data: EmailVerifyRequest) -> AuthActionResponse:
        user_result = await self.db.execute(select(AuthUser).where(AuthUser.email == data.email))
        user = user_result.scalar_one_or_none()

        if not user:
            return AuthActionResponse(ok=True)
        if bool(user.is_email_verified):
            return AuthActionResponse(ok=True)

        raw_token = generate_opaque_token()
        verify = EmailVerificationToken(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(verify)
        await self.db.commit()

        return AuthActionResponse(ok=True, debug_token=raw_token if _DEBUG else None)
    
    async def confirm_email_verification(self, data: EmailVerifyConfirmRequest) -> AuthActionResponse:
        token_hash = hash_token(data.token)
        token_result = await self.db.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
        )
        token_row = token_result.scalar_one_or_none()

        if not token_row:
            raise HTTPException(status_code=400, detail=ErrorMessage.INVALID_VERIFICATION_TOKEN)
        if token_row.used_at is not None:
            raise HTTPException(status_code=400, detail=ErrorMessage.VERIFICATION_TOKEN_ALREADY_USED)
        if token_row.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail=ErrorMessage.VERIFICATION_TOKEN_EXPIRED)

        user = await self.db.get(AuthUser, token_row.user_id)
        if not user:
            raise HTTPException(status_code=400, detail=ErrorMessage.USER_NOT_FOUND)

        user.is_email_verified = True
        token_row.used_at = datetime.now(timezone.utc)
        await self.db.commit()

        return AuthActionResponse(ok=True)