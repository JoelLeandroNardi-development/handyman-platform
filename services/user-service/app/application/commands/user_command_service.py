from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..mappers import to_response
from ...domain.events import build_event
from ...domain.models import User, OutboxEvent
from ...domain.schemas import CreateUser, UpdateUser, UpdateUserLocation, UserResponse
from shared.shared.crud_helpers import apply_partial_update, fetch_or_404
from shared.shared.outbox_helpers import add_outbox_event

class UserCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, data: CreateUser) -> UserResponse:
        existing = await self.db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="User already exists")

        u = User(
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            national_id=data.national_id,
            address_line=data.address_line,
            postal_code=data.postal_code,
            city=data.city,
            country=data.country,
            latitude=data.latitude,
            longitude=data.longitude,
        )
        self.db.add(u)

        add_outbox_event(self.db, OutboxEvent, build_event("user.created", data.model_dump()))

        await self.db.commit()
        await self.db.refresh(u)
        return to_response(u)
    
    async def update_user_location(self, email: str, data: UpdateUserLocation) -> UserResponse:
        u = await fetch_or_404(self.db, User, filter_column=User.email, filter_value=email, detail="User not found")

        u.latitude = data.latitude
        u.longitude = data.longitude

        evt = build_event(
            "user.location_updated",
            {
                "email": email,
                "latitude": data.latitude,
                "longitude": data.longitude,
            },
        )

        add_outbox_event(self.db, OutboxEvent, evt)

        await self.db.commit()
        await self.db.refresh(u)
        return to_response(u)

    async def update_user(self, email: str, data: UpdateUser) -> UserResponse:
        u = await fetch_or_404(self.db, User, filter_column=User.email, filter_value=email, detail="User not found")

        apply_partial_update(u, data, [
            "first_name", "last_name", "phone", "national_id",
            "address_line", "postal_code", "city", "country",
            "latitude", "longitude",
        ])

        evt = build_event(
            "user.updated",
            {
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone": u.phone,
                "national_id": u.national_id,
                "address_line": u.address_line,
                "postal_code": u.postal_code,
                "city": u.city,
                "country": u.country,
                "latitude": u.latitude,
                "longitude": u.longitude,
            },
        )

        add_outbox_event(self.db, OutboxEvent, evt)

        await self.db.commit()
        await self.db.refresh(u)
        return to_response(u)

    async def delete_user(self,email: str):
        u = await fetch_or_404(self.db, User, filter_column=User.email, filter_value=email, detail="User not found")

        add_outbox_event(self.db, OutboxEvent, build_event("user.deleted", {"email": email}))

        await self.db.delete(u)
        await self.db.commit()
        return {"message": "deleted", "email": email}