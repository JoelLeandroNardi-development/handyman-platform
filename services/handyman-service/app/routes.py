from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, delete, func

from .db import SessionLocal
from .models import Handyman, HandymanReview, OutboxEvent
from .schemas import (
    CreateHandyman,
    UpdateLocation,
    UpdateHandyman,
    HandymanResponse,
    SkillCatalogReplaceRequest,
    SkillCatalogPatchRequest,
    SkillCatalogFlatResponse,
    InvalidHandymanSkillsResponse,
    CreateHandymanReview,
    HandymanReviewResponse,
)
from .events import build_event
from shared.shared.outbox_helpers import add_outbox_event
from shared.shared.crud_helpers import fetch_or_404, apply_partial_update
from .skills_catalog import (
    get_grouped_catalog,
    get_catalog_flat,
    find_invalid_skills,
    normalize_skills_input,
    replace_catalog,
    patch_catalog,
    get_handymen_with_invalid_skills,
)

router = APIRouter()


def _to_response(h: Handyman) -> HandymanResponse:
    return HandymanResponse(
        email=h.email,
        first_name=h.first_name,
        last_name=h.last_name,
        phone=h.phone,
        national_id=h.national_id,
        address_line=h.address_line,
        postal_code=h.postal_code,
        city=h.city,
        country=h.country,
        skills=list(h.skills or []),
        years_experience=h.years_experience,
        service_radius_km=h.service_radius_km,
        latitude=h.latitude,
        longitude=h.longitude,
        avg_rating=float(h.avg_rating or 0),
        rating_count=int(h.rating_count or 0),
        created_at=h.created_at,
    )


def _review_to_response(r: HandymanReview) -> HandymanReviewResponse:
    return HandymanReviewResponse(
        id=r.id,
        booking_id=r.booking_id,
        handyman_email=r.handyman_email,
        user_email=r.user_email,
        rating=r.rating,
        review_text=r.review_text,
        created_at=r.created_at,
    )


async def _refresh_handyman_rating(db, handyman_email: str) -> None:
    res = await db.execute(
        select(
            func.count(HandymanReview.id),
            func.avg(HandymanReview.rating),
        ).where(HandymanReview.handyman_email == handyman_email)
    )
    count_value, avg_value = res.one()

    handyman_res = await db.execute(select(Handyman).where(Handyman.email == handyman_email))
    handyman = handyman_res.scalar_one_or_none()
    if handyman is None:
        return

    handyman.rating_count = int(count_value or 0)
    handyman.avg_rating = round(float(avg_value or 0), 2)


@router.get("/skills-catalog")
async def get_skills_catalog(
    active_only: bool = Query(True),
):
    return await get_grouped_catalog(active_only=active_only)


@router.get("/skills-catalog/flat", response_model=SkillCatalogFlatResponse)
async def get_skills_catalog_flat(
    active_only: bool = Query(True),
):
    return await get_catalog_flat(active_only=active_only)


@router.put("/admin/skills-catalog")
async def replace_skills_catalog(data: SkillCatalogReplaceRequest):
    try:
        return await replace_catalog(data.catalog)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/admin/skills-catalog")
async def patch_skills_catalog_endpoint(data: SkillCatalogPatchRequest):
    return await patch_catalog(data.model_dump())


@router.get("/admin/handymen/invalid-skills", response_model=InvalidHandymanSkillsResponse)
async def get_invalid_handyman_skills():
    return await get_handymen_with_invalid_skills()


@router.post("/handymen", response_model=HandymanResponse)
async def create_handyman(data: CreateHandyman):
    normalized_skills = normalize_skills_input(data.skills)
    invalid_skills = await find_invalid_skills(normalized_skills)
    if invalid_skills:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid handyman skills",
                "invalid_skills": invalid_skills,
            },
        )

    async with SessionLocal() as db:
        existing = await db.execute(select(Handyman).where(Handyman.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Handyman already exists")

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
        db.add(h)

        evt = build_event(
            "handyman.created",
            {
                "email": data.email,
                "first_name": data.first_name,
                "last_name": data.last_name,
                "phone": data.phone,
                "national_id": data.national_id,
                "address_line": data.address_line,
                "postal_code": data.postal_code,
                "city": data.city,
                "country": data.country,
                "skills": normalized_skills,
                "years_experience": data.years_experience,
                "service_radius_km": data.service_radius_km,
                "latitude": data.latitude,
                "longitude": data.longitude,
                "avg_rating": 0,
                "rating_count": 0,
            },
        )

        add_outbox_event(db, OutboxEvent, evt)

        await db.commit()
        await db.refresh(h)

        return _to_response(h)


@router.get("/handymen", response_model=list[HandymanResponse])
async def list_handymen(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    async with SessionLocal() as db:
        res = await db.execute(
            select(Handyman).order_by(Handyman.id.asc()).limit(limit).offset(offset)
        )
        rows = res.scalars().all()
        return [_to_response(h) for h in rows]


@router.get("/handymen/{email}", response_model=HandymanResponse)
async def get_handyman(email: str):
    async with SessionLocal() as db:
        h = await fetch_or_404(db, Handyman, filter_column=Handyman.email, filter_value=email, detail="Handyman not found")
        return _to_response(h)


@router.put("/handymen/{email}/location", response_model=HandymanResponse)
async def update_location(email: str, data: UpdateLocation):
    async with SessionLocal() as db:
        h = await fetch_or_404(db, Handyman, filter_column=Handyman.email, filter_value=email, detail="Handyman not found")

        h.latitude = data.latitude
        h.longitude = data.longitude

        evt = build_event(
            "handyman.location_updated",
            {"email": email, "latitude": data.latitude, "longitude": data.longitude},
        )

        add_outbox_event(db, OutboxEvent, evt)

        await db.commit()
        await db.refresh(h)
        return _to_response(h)


@router.put("/handymen/{email}", response_model=HandymanResponse)
async def update_handyman(email: str, data: UpdateHandyman):
    async with SessionLocal() as db:
        h = await fetch_or_404(db, Handyman, filter_column=Handyman.email, filter_value=email, detail="Handyman not found")

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
                        "message": "Invalid handyman skills",
                        "invalid_skills": invalid_skills,
                    },
                )
            h.skills = normalized_skills

        apply_partial_update(h, data, [
            "years_experience", "service_radius_km", "latitude", "longitude",
        ])

        evt = build_event(
            "handyman.updated",
            {
                "email": h.email,
                "first_name": h.first_name,
                "last_name": h.last_name,
                "phone": h.phone,
                "national_id": h.national_id,
                "address_line": h.address_line,
                "postal_code": h.postal_code,
                "city": h.city,
                "country": h.country,
                "skills": list(h.skills or []),
                "years_experience": h.years_experience,
                "service_radius_km": h.service_radius_km,
                "latitude": h.latitude,
                "longitude": h.longitude,
                "avg_rating": float(h.avg_rating or 0),
                "rating_count": int(h.rating_count or 0),
            },
        )

        add_outbox_event(db, OutboxEvent, evt)

        await db.commit()
        await db.refresh(h)
        return _to_response(h)


@router.delete("/handymen/{email}")
async def delete_handyman(email: str):
    async with SessionLocal() as db:
        h = await fetch_or_404(db, Handyman, filter_column=Handyman.email, filter_value=email, detail="Handyman not found")

        evt = build_event("handyman.deleted", {"email": email})

        add_outbox_event(db, OutboxEvent, evt)

        await db.execute(delete(Handyman).where(Handyman.email == email))
        await db.commit()

        return {"message": "deleted", "email": email}


@router.post("/handymen/reviews", response_model=HandymanReviewResponse)
async def create_handyman_review(data: CreateHandymanReview):
    async with SessionLocal() as db:
        handyman = await fetch_or_404(db, Handyman, filter_column=Handyman.email, filter_value=data.handyman_email, detail="Handyman not found")

        existing_res = await db.execute(
            select(HandymanReview).where(HandymanReview.booking_id == data.booking_id)
        )
        existing = existing_res.scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Review already exists for this booking")

        review = HandymanReview(
            booking_id=data.booking_id,
            handyman_email=data.handyman_email,
            user_email=data.user_email,
            rating=data.rating,
            review_text=data.review_text,
        )
        db.add(review)
        await db.flush()

        await _refresh_handyman_rating(db, data.handyman_email)

        await db.commit()
        await db.refresh(review)

        return _review_to_response(review)


@router.get("/handymen/{email}/reviews", response_model=list[HandymanReviewResponse])
async def list_handyman_reviews(
    email: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    async with SessionLocal() as db:
        handyman = await fetch_or_404(db, Handyman, filter_column=Handyman.email, filter_value=email, detail="Handyman not found")

        res = await db.execute(
            select(HandymanReview)
            .where(HandymanReview.handyman_email == email)
            .order_by(HandymanReview.created_at.desc(), HandymanReview.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = res.scalars().all()
        return [_review_to_response(r) for r in rows]