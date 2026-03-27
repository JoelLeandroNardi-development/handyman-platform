from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.models import AuthUser, AuthSession
from ...domain.schemas import Register, Login, RefreshRequest, GoogleLoginRequest
from ...infrastructure.password_hasher import password_hasher
from ...infrastructure.token_service import (
    JWTError,
    decode_token,
    generate_opaque_token,
    hash_token,
    issue_token_pair,
)
from shared.shared.schemas.auth import LogoutRequest

class AuthCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: Register) -> dict:
        result = await self.db.execute(select(AuthUser).where(AuthUser.email == data.email))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")

        user = AuthUser(
            email=data.email,
            password=password_hasher.hash(data.password),
            roles=data.roles,
            is_email_verified=False,
            auth_provider="local",
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return {"message": "User registered", "roles": user.roles}

    async def login(self, data: Login) -> dict:
        result = await self.db.execute(select(AuthUser).where(AuthUser.email == data.email))
        user = result.scalar_one_or_none()

        if not user or not password_hasher.verify(data.password, user.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        now = datetime.now(timezone.utc)
        session_id = str(uuid4())
        tokens = issue_token_pair(
            user_email=user.email,
            roles=list(user.roles or []),
            session_id=session_id,
        )

        user.last_login_at = now
        self.db.add(
            AuthSession(
                id=session_id,
                user_id=user.id,
                refresh_token_hash=hash_token(tokens.refresh_token),
                expires_at=tokens.refresh_expires_at,
            )
        )
        await self.db.commit()

        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": int((tokens.access_expires_at - now).total_seconds()),
        }
    
    async def refresh_tokens(self, data: RefreshRequest) -> dict:
        try:
            token_payload = decode_token(data.refresh_token)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        if token_payload.get("typ") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        sid = token_payload.get("sid")
        sub = token_payload.get("sub")
        roles = token_payload.get("roles") or []
        if not sid or not sub:
            raise HTTPException(status_code=401, detail="Malformed refresh token")

        session = await self.db.get(AuthSession, str(sid))
        if not session:
            raise HTTPException(status_code=401, detail="Session not found")

        now = datetime.now(timezone.utc)
        if session.revoked_at is not None:
            raise HTTPException(status_code=401, detail="Session revoked")
        if session.expires_at <= now:
            raise HTTPException(status_code=401, detail="Session expired")
        if session.refresh_token_hash != hash_token(data.refresh_token):
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        session.revoked_at = now

        user_result = await self.db.execute(select(AuthUser).where(AuthUser.email == str(sub)))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        new_session_id = str(uuid4())
        tokens = issue_token_pair(
            user_email=user.email,
            roles=list(user.roles or roles),
            session_id=new_session_id,
        )

        self.db.add(
            AuthSession(
                id=new_session_id,
                user_id=user.id,
                refresh_token_hash=hash_token(tokens.refresh_token),
                expires_at=tokens.refresh_expires_at,
                last_seen_at=now,
            )
        )
        await self.db.commit()

        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": int((tokens.access_expires_at - now).total_seconds()),
        }
    
    async def logout(self, data: LogoutRequest) -> dict:
        try:
            token_payload = decode_token(data.refresh_token)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        sid = token_payload.get("sid")
        if not sid:
            raise HTTPException(status_code=401, detail="Malformed refresh token")

        session = await self.db.get(AuthSession, str(sid))
        if not session:
            return {"ok": True}

        if session.refresh_token_hash != hash_token(data.refresh_token):
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        if session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()

        return {"ok": True}
    
    async def google_login(self, data: GoogleLoginRequest) -> dict:
        client_id = self.os.getenv("GOOGLE_CLIENT_ID")
        if not client_id:
            raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID is not configured")

        try:
            from google.auth.transport.requests import Request as GoogleRequest
            from google.oauth2 import id_token as google_id_token

            token_payload = google_id_token.verify_oauth2_token(
                data.id_token,
                GoogleRequest(),
                audience=client_id,
            )
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid Google ID token")

        issuer = token_payload.get("iss")
        if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
            raise HTTPException(status_code=401, detail="Invalid Google token issuer")

        email = str(token_payload.get("email") or "").strip().lower()
        google_sub = str(token_payload.get("sub") or "").strip()
        email_verified = bool(token_payload.get("email_verified"))

        if not email or not google_sub:
            raise HTTPException(status_code=401, detail="Google token missing required claims")
        if not email_verified:
            raise HTTPException(status_code=401, detail="Google account email is not verified")

        user = (
            await self.db.execute(select(AuthUser).where(AuthUser.google_sub == google_sub))
        ).scalar_one_or_none()
        is_new_user = False

        if not user:
            user = (await self.db.execute(select(AuthUser).where(AuthUser.email == email))).scalar_one_or_none()

        if not user:
            is_new_user = True
            user = AuthUser(
                email=email,
                password=password_hasher.hash(generate_opaque_token()),
                roles=["user"],
                is_email_verified=True,
                auth_provider="google",
                google_sub=google_sub,
            )
            self.db.add(user)
            await self.db.flush()
        else:
            if not user.google_sub:
                user.google_sub = google_sub
            user.is_email_verified = bool(user.is_email_verified) or email_verified
            if not user.auth_provider:
                user.auth_provider = "google"

        now = datetime.now(timezone.utc)
        user.last_login_at = now

        session_id = str(uuid4())
        roles = list(user.roles or ["user"])
        tokens = issue_token_pair(
            user_email=user.email,
            roles=roles,
            session_id=session_id,
        )

        self.db.add(
            AuthSession(
                id=session_id,
                user_id=user.id,
                refresh_token_hash=hash_token(tokens.refresh_token),
                expires_at=tokens.refresh_expires_at,
            )
        )
        await self.db.commit()

        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": int((tokens.access_expires_at - now).total_seconds()),
            "is_new_user": is_new_user,
            "email": user.email,
            "roles": roles,
        }