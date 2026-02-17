from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .db import SessionLocal
from .models import Handyman
from .schemas import CreateHandyman, UpdateLocation

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

    db.add(handyman)
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
