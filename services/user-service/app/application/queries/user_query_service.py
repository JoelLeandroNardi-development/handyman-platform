from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.mappers import _to_response
from app.domain.models import User
from app.domain.schemas import UserResponse
from shared.shared.crud_helpers import fetch_or_404

class UserQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def list_users(self, limit: int, offset: int) -> list[UserResponse]:
        res = await self.db.execute(select(User).order_by(User.id.asc()).limit(limit).offset(offset))
        rows = res.scalars().all()
        return [_to_response(u) for u in rows]

    async def get_user(self, email: str) -> UserResponse:
        u = await fetch_or_404(self.db, User, filter_column=User.email, filter_value=email, detail="User not found")
        return _to_response(u)