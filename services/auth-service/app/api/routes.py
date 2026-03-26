from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import SessionLocal
from app.domain.schemas import (
    Register,
    Login,
    GoogleLoginRequest,
    GoogleLoginResponse,
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
from shared.shared.db import make_get_db
from app.application.auth_service import AuthService
from app.application.verification_service import VerificationService
from app.application.auth_user_service import AuthUserService

router = APIRouter()
get_db = make_get_db(SessionLocal)

@router.post("/register")
async def register(data: Register, db: AsyncSession = Depends(get_db)):
    return await AuthService(db).register(data)

@router.post("/login", response_model=TokenPairResponse)
async def login(data: Login, db: AsyncSession = Depends(get_db)):
    return await AuthService(db).login(data)

@router.post("/auth/google", response_model=GoogleLoginResponse)
async def google_login(payload: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    return await AuthService(db).google_login(payload)

@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_tokens(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await AuthService(db).refresh_tokens(payload)

@router.post("/logout")
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    return await AuthService(db).logout(payload)

@router.post("/password/forgot", response_model=AuthActionResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    return await VerificationService(db).forgot_password(payload.email)

@router.post("/password/reset", response_model=AuthActionResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    return await VerificationService(db).reset_password(payload)

@router.post("/email/verify/request", response_model=AuthActionResponse)
async def request_email_verification(payload: EmailVerifyRequest, db: AsyncSession = Depends(get_db)):
    return await VerificationService(db).request_email_verification(payload)

@router.post("/email/verify/confirm", response_model=AuthActionResponse)
async def confirm_email_verification(payload: EmailVerifyConfirmRequest, db: AsyncSession = Depends(get_db)):
    return await VerificationService(db).confirm_email_verification(payload)

@router.get("/auth-users", response_model=list[AuthUserResponse])
async def list_auth_users(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await AuthUserService(db).list_users(limit, offset)

@router.get("/auth-users/{user_id}", response_model=AuthUserResponse)
async def get_auth_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await AuthUserService(db).get_by_id(user_id)

@router.get("/auth-users/by-email/{email}", response_model=AuthUserResponse)
async def get_auth_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    return await AuthUserService(db).get_auth_user_by_email(email)

@router.put("/auth-users/{user_id}", response_model=AuthUserResponse)
async def update_auth_user(
    user_id: int,
    data: UpdateAuthUser,
    db: AsyncSession = Depends(get_db),
):
    return await AuthUserService(db).update_auth_user(user_id, data)

@router.delete("/auth-users/{user_id}")
async def delete_auth_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await AuthUserService(db).delete_auth_user(user_id)