from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..mappers import to_response
from ...domain.constants import DataKey, ErrorMessage, ResponseMessage, UserEventType
from ...domain.events import build_event
from ...domain.models import User, OutboxEvent
from ...domain.schemas import CreateUser, UpdateUser, UpdateUserLocation, UserResponse
from shared.core.db.crud import apply_partial_update, fetch_or_404
from shared.core.outbox.helpers import add_outbox_event

class UserCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, data: CreateUser) -> UserResponse:
        existing = await self.db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=ErrorMessage.USER_ALREADY_EXISTS)

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

        add_outbox_event(self.db, OutboxEvent, build_event(UserEventType.CREATED, data.model_dump()))

        await self.db.commit()
        await self.db.refresh(u)
        return to_response(u)
    
    async def update_user_location(self, email: str, data: UpdateUserLocation) -> UserResponse:
        u = await fetch_or_404(self.db, User, filter_column=User.email, filter_value=email, detail=ErrorMessage.USER_NOT_FOUND)

        u.latitude = data.latitude
        u.longitude = data.longitude

        evt = build_event(
            UserEventType.LOCATION_UPDATED,
            {
                DataKey.EMAIL: email,
                DataKey.LATITUDE: data.latitude,
                DataKey.LONGITUDE: data.longitude,
            },
        )

        add_outbox_event(self.db, OutboxEvent, evt)

        await self.db.commit()
        await self.db.refresh(u)
        return to_response(u)

    async def update_user(self, email: str, data: UpdateUser) -> UserResponse:
        u = await fetch_or_404(self.db, User, filter_column=User.email, filter_value=email, detail=ErrorMessage.USER_NOT_FOUND)

        apply_partial_update(u, data, [
            "first_name", "last_name", "phone", "national_id",
            "address_line", "postal_code", "city", "country",
            "latitude", "longitude",
        ])

        evt = build_event(
            UserEventType.UPDATED,
            {
                DataKey.EMAIL: u.email,
                DataKey.FIRST_NAME: u.first_name,
                DataKey.LAST_NAME: u.last_name,
                DataKey.PHONE: u.phone,
                DataKey.NATIONAL_ID: u.national_id,
                DataKey.ADDRESS_LINE: u.address_line,
                DataKey.POSTAL_CODE: u.postal_code,
                DataKey.CITY: u.city,
                DataKey.COUNTRY: u.country,
                DataKey.LATITUDE: u.latitude,
                DataKey.LONGITUDE: u.longitude,
            },
        )

        add_outbox_event(self.db, OutboxEvent, evt)

        await self.db.commit()
        await self.db.refresh(u)
        return to_response(u)

    async def delete_user(self,email: str):
        u = await fetch_or_404(self.db, User, filter_column=User.email, filter_value=email, detail=ErrorMessage.USER_NOT_FOUND)

        add_outbox_event(self.db, OutboxEvent, build_event(UserEventType.DELETED, {DataKey.EMAIL: email}))

        await self.db.delete(u)
        await self.db.commit()
        return {"message": ResponseMessage.DELETED, DataKey.EMAIL: email}