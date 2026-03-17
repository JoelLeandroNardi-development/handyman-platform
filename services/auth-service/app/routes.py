import os
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext

from .db import SessionLocal
from .models import AuthSession, AuthUser, EmailVerificationToken, PasswordResetToken
from .schemas import (
    Register,
    Login,
    TokenPairResponse,
    RefreshRequest,
    LogoutRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    EmailVerifyRequest,
    EmailVerifyConfirmRequest,
    AuthActionResponse,
    AuthUserResponse,
    UpdateAuthUser,
)
from .token_service import JWTError, decode_token, generate_opaque_token, hash_token, issue_token_pair
from shared.shared.crud_helpers import fetch_or_404

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"])

async def get_db():
    async with SessionLocal() as session:
        yield session


def _to_response(u: AuthUser) -> AuthUserResponse:
    return AuthUserResponse(
        id=u.id,
        email=u.email,
        roles=list(u.roles or []),
        is_email_verified=bool(u.is_email_verified),
        auth_provider=str(u.auth_provider or "local"),
        google_sub=u.google_sub,
        last_login_at=u.last_login_at,
    )


@router.post("/register")
async def register(data: Register, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuthUser).where(AuthUser.email == data.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    hashed = pwd_context.hash(data.password)

    user = AuthUser(
        email=data.email,
        password=hashed,
        roles=data.roles,
        is_email_verified=False,
        auth_provider="local",
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"message": "User registered", "roles": user.roles}


@router.post("/login", response_model=TokenPairResponse)
async def login(data: Login, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuthUser).where(AuthUser.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not pwd_context.verify(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    now = datetime.now(timezone.utc)
    session_id = str(uuid4())
    tokens = issue_token_pair(
        user_email=user.email,
        roles=list(user.roles or []),
        session_id=session_id,
    )

    user.last_login_at = now

    session = AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=hash_token(tokens.refresh_token),
        expires_at=tokens.refresh_expires_at,
    )
    db.add(session)
    await db.commit()

    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_in": int((tokens.access_expires_at - now).total_seconds()),
    }


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_tokens(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if token_payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    sid = token_payload.get("sid")
    sub = token_payload.get("sub")
    roles = token_payload.get("roles") or []
    if not sid or not sub:
        raise HTTPException(status_code=401, detail="Malformed refresh token")

    session = await db.get(AuthSession, str(sid))
    if not session:
        raise HTTPException(status_code=401, detail="Session not found")

    now = datetime.now(timezone.utc)
    if session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Session revoked")
    if session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Session expired")
    if session.refresh_token_hash != hash_token(payload.refresh_token):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    session.revoked_at = now

    user_result = await db.execute(select(AuthUser).where(AuthUser.email == str(sub)))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_session_id = str(uuid4())
    tokens = issue_token_pair(
        user_email=user.email,
        roles=list(user.roles or roles),
        session_id=new_session_id,
    )

    db.add(
        AuthSession(
            id=new_session_id,
            user_id=user.id,
            refresh_token_hash=hash_token(tokens.refresh_token),
            expires_at=tokens.refresh_expires_at,
            last_seen_at=now,
        )
    )
    await db.commit()

    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_in": int((tokens.access_expires_at - now).total_seconds()),
    }


@router.post("/logout")
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    sid = token_payload.get("sid")
    if not sid:
        raise HTTPException(status_code=401, detail="Malformed refresh token")

    session = await db.get(AuthSession, str(sid))
    if not session:
        return {"ok": True}

    if session.refresh_token_hash != hash_token(payload.refresh_token):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        await db.commit()

    return {"ok": True}


@router.post("/password/forgot", response_model=AuthActionResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    user_result = await db.execute(select(AuthUser).where(AuthUser.email == payload.email))
    user = user_result.scalar_one_or_none()

    if not user:
        return {"ok": True}

    raw_token = generate_opaque_token()
    reset = PasswordResetToken(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1),
    )
    db.add(reset)
    await db.commit()

    return {"ok": True, "debug_token": raw_token}


@router.post("/password/reset", response_model=AuthActionResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.token)
    token_result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    token_row = token_result.scalar_one_or_none()

    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    if token_row.used_at is not None:
        raise HTTPException(status_code=400, detail="Reset token already used")
    if token_row.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token expired")

    user = await db.get(AuthUser, token_row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.password = pwd_context.hash(payload.new_password)
    token_row.used_at = datetime.now(timezone.utc)
    await db.commit()

    return {"ok": True}


@router.post("/email/verify/request", response_model=AuthActionResponse)
async def request_email_verification(payload: EmailVerifyRequest, db: AsyncSession = Depends(get_db)):
    user_result = await db.execute(select(AuthUser).where(AuthUser.email == payload.email))
    user = user_result.scalar_one_or_none()

    if not user:
        return {"ok": True}
    if bool(user.is_email_verified):
        return {"ok": True}

    raw_token = generate_opaque_token()
    verify = EmailVerificationToken(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=24),
    )
    db.add(verify)
    await db.commit()

    return {"ok": True, "debug_token": raw_token}


@router.post("/email/verify/confirm", response_model=AuthActionResponse)
async def confirm_email_verification(payload: EmailVerifyConfirmRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.token)
    token_result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    token_row = token_result.scalar_one_or_none()

    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    if token_row.used_at is not None:
        raise HTTPException(status_code=400, detail="Verification token already used")
    if token_row.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification token expired")

    user = await db.get(AuthUser, token_row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.is_email_verified = True
    token_row.used_at = datetime.now(timezone.utc)
    await db.commit()

    return {"ok": True}


@router.get("/auth-users", response_model=list[AuthUserResponse])
async def list_auth_users(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(AuthUser).order_by(AuthUser.id.asc()).limit(limit).offset(offset)
    )
    rows = res.scalars().all()
    return [_to_response(u) for u in rows]


@router.get("/auth-users/{user_id}", response_model=AuthUserResponse)
async def get_auth_user(user_id: int, db: AsyncSession = Depends(get_db)):
    u = await fetch_or_404(db, AuthUser, filter_column=AuthUser.id, filter_value=user_id, detail="Auth user not found")
    return _to_response(u)


@router.get("/auth-users/by-email/{email}", response_model=AuthUserResponse)
async def get_auth_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    u = await fetch_or_404(db, AuthUser, filter_column=AuthUser.email, filter_value=email, detail="Auth user not found")
    return _to_response(u)


@router.put("/auth-users/{user_id}", response_model=AuthUserResponse)
async def update_auth_user(
    user_id: int,
    data: UpdateAuthUser,
    db: AsyncSession = Depends(get_db),
):
    u = await fetch_or_404(db, AuthUser, filter_column=AuthUser.id, filter_value=user_id, detail="Auth user not found")

    if data.password is not None:
        u.password = pwd_context.hash(data.password)

    if data.roles is not None:
        u.roles = data.roles

    await db.commit()
    await db.refresh(u)
    return _to_response(u)


@router.delete("/auth-users/{user_id}")
async def delete_auth_user(user_id: int, db: AsyncSession = Depends(get_db)):
    u = await fetch_or_404(db, AuthUser, filter_column=AuthUser.id, filter_value=user_id, detail="Auth user not found")

    await db.execute(delete(AuthUser).where(AuthUser.id == user_id))
    await db.commit()

    return {"message": "deleted", "user_id": user_id}