from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .db import SessionLocal
from .models import Handyman, OutboxEvent
from .schemas import CreateHandyman, UpdateLocation
from .events import build_event

router = APIRouter()


async def get_db():
    async with SessionLocal() as session:
        yield session


@router.post("/handymen")
async def create_handyman(data: CreateHandyman, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Handyman).where(Handyman.email == data.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Handyman already exists")

    handyman = Handyman(
        email=data.email,
        skills=data.skills,
        years_experience=data.years_experience,
        service_radius_km=data.service_radius_km,
        latitude=data.latitude,
        longitude=data.longitude,
    )

    event = build_event(
        "handyman.created",
        {
            "email": handyman.email,
            "skills": handyman.skills,
            "years_experience": handyman.years_experience,
            "service_radius_km": handyman.service_radius_km,
            "latitude": handyman.latitude,
            "longitude": handyman.longitude,
        },
    )

    db.add(handyman)
    db.add(
        OutboxEvent(
            event_id=event["event_id"],
            event_type=event["event_type"],
            routing_key="handyman.created",
            payload=event,
            status="PENDING",
        )
    )

    await db.commit()
    return {"message": "Handyman created"}


@router.put("/handymen/{email}/location")
async def update_location(email: str, data: UpdateLocation, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Handyman).where(Handyman.email == email))
    handyman = result.scalar_one_or_none()

    if not handyman:
        raise HTTPException(status_code=404, detail="Handyman not found")

    handyman.latitude = data.latitude
    handyman.longitude = data.longitude
    await db.commit()

    event = build_event(
        "handyman.location_updated",
        {
            "email": handyman.email,
            "skills": handyman.skills,
            "service_radius_km": handyman.service_radius_km,
            "latitude": handyman.latitude,
            "longitude": handyman.longitude,
        },
    )

    db.add(
        OutboxEvent(
            event_id=event["event_id"],
            event_type=event["event_type"],
            routing_key="handyman.location_updated",
            payload=event,
            status="PENDING",
        )
    )

    await db.commit()
    return {"message": "Location updated"}


@router.get("/handymen/{email}")
async def get_handyman(email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Handyman).where(Handyman.email == email))
    handyman = result.scalar_one_or_none()

    if not handyman:
        raise HTTPException(status_code=404, detail="Handyman not found")

    return {
        "email": handyman.email,
        "skills": handyman.skills,
        "years_experience": handyman.years_experience,
        "service_radius_km": handyman.service_radius_km,
        "latitude": handyman.latitude,
        "longitude": handyman.longitude,
    }


@router.get("/handymen")
async def list_handymen(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Handyman))
    handymen = result.scalars().all()

    return [
        {
            "email": h.email,
            "skills": h.skills,
            "years_experience": h.years_experience,
            "service_radius_km": h.service_radius_km,
            "latitude": h.latitude,
            "longitude": h.longitude,
        }
        for h in handymen
    ]