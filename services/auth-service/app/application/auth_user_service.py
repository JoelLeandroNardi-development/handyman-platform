from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AuthUser
from app.domain.schemas import AuthUserResponse, UpdateAuthUser
from app.infrastructure.password_hasher import password_hasher
from shared.shared.crud_helpers import fetch_or_404

def to_auth_user_response(u: AuthUser) -> AuthUserResponse:
    return AuthUserResponse(
        id=u.id,
        email=u.email,
        roles=list(u.roles or []),
        is_email_verified=bool(u.is_email_verified),
        auth_provider=str(u.auth_provider or "local"),
        google_sub=u.google_sub,
        last_login_at=u.last_login_at,
    )

class AuthUserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self, limit: int, offset: int) -> list[AuthUserResponse]:
        res = await self.db.execute(
            select(AuthUser).order_by(AuthUser.id.asc()).limit(limit).offset(offset)
        )
        return [to_auth_user_response(u) for u in res.scalars().all()]

    async def get_by_id(self, user_id: int) -> AuthUserResponse:
        u = await fetch_or_404(
            self.db,
            AuthUser,
            filter_column=AuthUser.id,
            filter_value=user_id,
            detail="Auth user not found",
        )
        return to_auth_user_response(u)
    
    async def get_auth_user_by_email(self, email: str) -> AuthUserResponse:
        u = await fetch_or_404(self.db, AuthUser, filter_column=AuthUser.email, filter_value=email, detail="Auth user not found")
        return to_auth_user_response(u)
    
    async def update_auth_user(
        self,
        user_id: int,
        data: UpdateAuthUser,
    ) -> AuthUserResponse:
        u = await fetch_or_404(self.db, AuthUser, filter_column=AuthUser.id, filter_value=user_id, detail="Auth user not found")

        if data.password is not None:
            u.password = password_hasher.hash(data.password)

        if data.roles is not None:
            u.roles = data.roles

        await self.db.commit()
        await self.db.refresh(u)
        return to_auth_user_response(u)
    
    async def delete_auth_user(self, user_id: int) -> dict:
        u = await fetch_or_404(self.db, AuthUser, filter_column=AuthUser.id, filter_value=user_id, detail="Auth user not found")

        await self.db.delete(u)
        await self.db.commit()

        return {"message": "deleted", "user_id": user_id}