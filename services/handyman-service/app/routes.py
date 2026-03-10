from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, delete

from .db import SessionLocal
from .models import Handyman, OutboxEvent
from .schemas import (
    CreateHandyman,
    UpdateLocation,
    UpdateHandyman,
    HandymanResponse,
    SkillCatalogReplaceRequest,
    SkillCatalogPatchRequest,
    SkillCatalogFlatResponse,
    InvalidHandymanSkillsResponse,
)
from .events import build_event
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
        skills=list(h.skills or []),
        years_experience=h.years_experience,
        service_radius_km=h.service_radius_km,
        latitude=h.latitude,
        longitude=h.longitude,
        created_at=h.created_at,
    )


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
async def patch_skills_catalog(data: SkillCatalogPatchRequest):
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
            skills=normalized_skills,
            years_experience=data.years_experience,
            service_radius_km=data.service_radius_km,
            latitude=data.latitude,
            longitude=data.longitude,
        )
        db.add(h)

        evt = build_event(
            "handyman.created",
            {
                "email": data.email,
                "skills": normalized_skills,
                "years_experience": data.years_experience,
                "service_radius_km": data.service_radius_km,
                "latitude": data.latitude,
                "longitude": data.longitude,
            },
        )

        db.add(
            OutboxEvent(
                event_id=evt["event_id"],
                event_type=evt["event_type"],
                routing_key=evt["event_type"],
                payload=evt,
                status="PENDING",
            )
        )

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
        res = await db.execute(select(Handyman).where(Handyman.email == email))
        h = res.scalar_one_or_none()
        if not h:
            raise HTTPException(status_code=404, detail="Handyman not found")
        return _to_response(h)


@router.put("/handymen/{email}/location", response_model=HandymanResponse)
async def update_location(email: str, data: UpdateLocation):
    async with SessionLocal() as db:
        res = await db.execute(select(Handyman).where(Handyman.email == email))
        h = res.scalar_one_or_none()
        if not h:
            raise HTTPException(status_code=404, detail="Handyman not found")

        h.latitude = data.latitude
        h.longitude = data.longitude

        evt = build_event(
            "handyman.location_updated",
            {"email": email, "latitude": data.latitude, "longitude": data.longitude},
        )

        db.add(
            OutboxEvent(
                event_id=evt["event_id"],
                event_type=evt["event_type"],
                routing_key=evt["event_type"],
                payload=evt,
                status="PENDING",
            )
        )

        await db.commit()
        await db.refresh(h)
        return _to_response(h)


@router.put("/handymen/{email}", response_model=HandymanResponse)
async def update_handyman(email: str, data: UpdateHandyman):
    async with SessionLocal() as db:
        res = await db.execute(select(Handyman).where(Handyman.email == email))
        h = res.scalar_one_or_none()
        if not h:
            raise HTTPException(status_code=404, detail="Handyman not found")

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

        if data.years_experience is not None:
            h.years_experience = data.years_experience
        if data.service_radius_km is not None:
            h.service_radius_km = data.service_radius_km
        if data.latitude is not None:
            h.latitude = data.latitude
        if data.longitude is not None:
            h.longitude = data.longitude

        evt = build_event(
            "handyman.updated",
            {
                "email": h.email,
                "skills": list(h.skills or []),
                "years_experience": h.years_experience,
                "service_radius_km": h.service_radius_km,
                "latitude": h.latitude,
                "longitude": h.longitude,
            },
        )

        db.add(
            OutboxEvent(
                event_id=evt["event_id"],
                event_type=evt["event_type"],
                routing_key=evt["event_type"],
                payload=evt,
                status="PENDING",
            )
        )

        await db.commit()
        await db.refresh(h)
        return _to_response(h)


@router.delete("/handymen/{email}")
async def delete_handyman(email: str):
    async with SessionLocal() as db:
        res = await db.execute(select(Handyman).where(Handyman.email == email))
        h = res.scalar_one_or_none()
        if not h:
            raise HTTPException(status_code=404, detail="Handyman not found")

        evt = build_event("handyman.deleted", {"email": email})

        db.add(
            OutboxEvent(
                event_id=evt["event_id"],
                event_type=evt["event_type"],
                routing_key=evt["event_type"],
                payload=evt,
                status="PENDING",
            )
        )

        await db.execute(delete(Handyman).where(Handyman.email == email))
        await db.commit()

        return {"message": "deleted", "email": email}