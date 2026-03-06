from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from .db import SessionLocal
from .models import User, OutboxEvent
from .schemas import CreateUser, UpdateLocation, UpdateUser, UserResponse
from .events import build_event

router = APIRouter()


async def get_db():
    async with SessionLocal() as session:
        yield session


def to_response(u: User) -> UserResponse:
    return UserResponse(
        email=u.email,
        full_name=u.full_name,
        latitude=u.latitude,
        longitude=u.longitude,
        created_at=u.created_at,
    )


@router.post("/users", response_model=UserResponse)
async def create_user(data: CreateUser, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == data.email))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already exists")

    user = User(
        email=data.email,
        full_name=data.full_name,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(user)

    event = build_event(
        "user.created",
        {
            "email": user.email,
            "full_name": user.full_name,
            "latitude": user.latitude,
            "longitude": user.longitude,
        },
    )

    db.add(
        OutboxEvent(
            event_id=event["event_id"],
            event_type=event["event_type"],
            routing_key=event["event_type"],
            payload=event,
            status="PENDING",
        )
    )

    await db.commit()
    await db.refresh(user)
    return to_response(user)


@router.put("/users/{email}/location", response_model=UserResponse)
async def update_location(email: str, data: UpdateLocation, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.latitude = data.latitude
    user.longitude = data.longitude

    event = build_event(
        "user.location_updated",
        {
            "email": user.email,
            "latitude": user.latitude,
            "longitude": user.longitude,
        },
    )

    db.add(
        OutboxEvent(
            event_id=event["event_id"],
            event_type=event["event_type"],
            routing_key=event["event_type"],
            payload=event,
            status="PENDING",
        )
    )

    await db.commit()
    await db.refresh(user)
    return to_response(user)


@router.get("/users/{email}", response_model=UserResponse)
async def get_user(email: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return to_response(user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(User).order_by(User.id.asc()).limit(limit).offset(offset))
    rows = res.scalars().all()
    return [to_response(u) for u in rows]


@router.put("/users/{email}", response_model=UserResponse)
async def update_user(email: str, data: UpdateUser, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.latitude is not None:
        user.latitude = data.latitude
    if data.longitude is not None:
        user.longitude = data.longitude

    event = build_event(
        "user.updated",
        {
            "email": user.email,
            "full_name": user.full_name,
            "latitude": user.latitude,
            "longitude": user.longitude,
        },
    )

    db.add(
        OutboxEvent(
            event_id=event["event_id"],
            event_type=event["event_type"],
            routing_key=event["event_type"],
            payload=event,
            status="PENDING",
        )
    )

    await db.commit()
    await db.refresh(user)
    return to_response(user)


@router.delete("/users/{email}")
async def delete_user(email: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    event = build_event("user.deleted", {"email": email})

    db.add(
        OutboxEvent(
            event_id=event["event_id"],
            event_type=event["event_type"],
            routing_key=event["event_type"],
            payload=event,
            status="PENDING",
        )
    )

    await db.execute(delete(User).where(User.email == email))
    await db.commit()

    return {"message": "deleted", "email": email}