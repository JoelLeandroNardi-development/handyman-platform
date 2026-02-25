from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .db import SessionLocal
from .models import User
from .schemas import CreateUser, UpdateLocation

from .events import build_event, to_json
from .rabbitmq import publisher

router = APIRouter()


async def get_db():
    async with SessionLocal() as session:
        yield session


@router.post("/users")
async def create_user(data: CreateUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(
        email=data.email,
        full_name=data.full_name,
        latitude=data.latitude,
        longitude=data.longitude,
    )

    db.add(user)
    await db.commit()

    event = build_event(
        "user.created",
        {
            "email": user.email,
            "full_name": user.full_name,
            "latitude": user.latitude,
            "longitude": user.longitude,
        },
    )
    await publisher.publish("user.created", to_json(event))

    return {"message": "User created"}


@router.put("/users/{email}/location")
async def update_location(email: str, data: UpdateLocation, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.latitude = data.latitude
    user.longitude = data.longitude

    await db.commit()

    event = build_event(
        "user.location_updated",
        {
            "email": user.email,
            "latitude": user.latitude,
            "longitude": user.longitude,
        },
    )
    await publisher.publish("user.location_updated", to_json(event))

    return {"message": "Location updated"}


@router.get("/users/{email}")
async def get_user(email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "email": user.email,
        "full_name": user.full_name,
        "latitude": user.latitude,
        "longitude": user.longitude,
    }
