from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from .db import SessionLocal
from .models import Handyman, OutboxEvent
from .schemas import CreateHandyman, UpdateLocation, HandymanResponse
from .events import build_event

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


@router.post("/handymen", response_model=HandymanResponse)
async def create_handyman(data: CreateHandyman):
    async with SessionLocal() as db:
        existing = await db.execute(select(Handyman).where(Handyman.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Handyman already exists")

        h = Handyman(
            email=data.email,
            skills=data.skills,
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
                "skills": data.skills,
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
async def list_handymen():
    async with SessionLocal() as db:
        res = await db.execute(select(Handyman).order_by(Handyman.id.asc()))
        handymen = res.scalars().all()
        return [_to_response(h) for h in handymen]


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