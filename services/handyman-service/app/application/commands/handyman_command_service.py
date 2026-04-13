from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers import find_invalid_skills, normalize_skills_input, refresh_handyman_rating
from ..mappers import handyman_event_data, to_response, review_to_response
from ...domain.constants import DataKey, ErrorMessage, HandymanEventType, ResponseMessage
from ...domain.events import build_event
from ...domain.models import Handyman, HandymanReview, OutboxEvent
from ...domain.schemas import (
    CreateHandyman, HandymanResponse, UpdateLocation, 
    UpdateHandyman, CreateHandymanReview, HandymanReviewResponse
)
from shared.core.db.crud import apply_partial_update, fetch_or_404
from shared.core.outbox.helpers import add_outbox_event

class HandymanCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_handyman(self, data: CreateHandyman) -> HandymanResponse:
        normalized_skills = normalize_skills_input(data.skills)
        invalid_skills = await find_invalid_skills(normalized_skills)
        if invalid_skills:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": ErrorMessage.INVALID_HANDYMAN_SKILLS,
                    "invalid_skills": invalid_skills,
                },
            )

        existing = await self.db.execute(select(Handyman).where(Handyman.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=ErrorMessage.HANDYMAN_ALREADY_EXISTS)

        h = Handyman(
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            national_id=data.national_id,
            address_line=data.address_line,
            postal_code=data.postal_code,
            city=data.city,
            country=data.country,
            skills=normalized_skills,
            years_experience=data.years_experience,
            service_radius_km=data.service_radius_km,
            latitude=data.latitude,
            longitude=data.longitude,
            avg_rating=0,
            rating_count=0,
        )
        self.db.add(h)

        evt = build_event(HandymanEventType.CREATED, handyman_event_data(h))

        add_outbox_event(self.db, OutboxEvent, evt)

        await self.db.commit()
        await self.db.refresh(h)

        return to_response(h)
    
    async def update_location(self, email: str, data: UpdateLocation) -> HandymanResponse: 
        h = await fetch_or_404(self.db, Handyman, filter_column=Handyman.email, filter_value=email, detail=ErrorMessage.HANDYMAN_NOT_FOUND)

        h.latitude = data.latitude
        h.longitude = data.longitude

        evt = build_event(
            HandymanEventType.LOCATION_UPDATED,
            {DataKey.EMAIL: email, DataKey.LATITUDE: data.latitude, DataKey.LONGITUDE: data.longitude},
        )

        add_outbox_event(self.db, OutboxEvent, evt)

        await self.db.commit()
        await self.db.refresh(h)
        return to_response(h)

    async def update_handyman(self, email: str, data: UpdateHandyman) -> HandymanResponse:
        h = await fetch_or_404(self.db, Handyman, filter_column=Handyman.email, filter_value=email, detail=ErrorMessage.HANDYMAN_NOT_FOUND)

        apply_partial_update(h, data, [
            "first_name", "last_name", "phone", "national_id",
            "address_line", "postal_code", "city", "country",
        ])

        if data.skills is not None:
            normalized_skills = normalize_skills_input(data.skills)
            invalid_skills = await find_invalid_skills(normalized_skills)
            if invalid_skills:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": ErrorMessage.INVALID_HANDYMAN_SKILLS,
                        "invalid_skills": invalid_skills,
                    },
                )
            h.skills = normalized_skills

        apply_partial_update(h, data, [
            "years_experience", "service_radius_km", "latitude", "longitude",
        ])

        evt = build_event(HandymanEventType.UPDATED, handyman_event_data(h))

        add_outbox_event(self.db, OutboxEvent, evt)

        await self.db.commit()
        await self.db.refresh(h)
        return to_response(h)

    async def delete_handyman(self, email: str):
        h = await fetch_or_404(self.db, Handyman, filter_column=Handyman.email, filter_value=email, detail=ErrorMessage.HANDYMAN_NOT_FOUND)

        evt = build_event(HandymanEventType.DELETED, {DataKey.EMAIL: email})

        add_outbox_event(self.db, OutboxEvent, evt)

        await self.db.execute(delete(Handyman).where(Handyman.email == email))
        await self.db.commit()

        return {"message": ResponseMessage.DELETED, DataKey.EMAIL: email}
    
    async def create_handyman_review(self, data: CreateHandymanReview) -> HandymanReviewResponse:
        handyman = await fetch_or_404(self.db, Handyman, filter_column=Handyman.email, filter_value=data.handyman_email, detail=ErrorMessage.HANDYMAN_NOT_FOUND)

        existing_res = await self.db.execute(
            select(HandymanReview).where(HandymanReview.booking_id == data.booking_id)
        )
        existing = existing_res.scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail=ErrorMessage.REVIEW_ALREADY_EXISTS)

        review = HandymanReview(
            booking_id=data.booking_id,
            handyman_email=data.handyman_email,
            user_email=data.user_email,
            rating=data.rating,
            review_text=data.review_text,
        )
        self.db.add(review)
        await self.db.flush()

        await refresh_handyman_rating(self.db, data.handyman_email)

        await self.db.commit()
        await self.db.refresh(review)

        return review_to_response(review)