from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from .db import SessionLocal
from .models import User, OutboxEvent
from .schemas import CreateUser, UpdateUserLocation, UpdateUser, UserResponse
from .events import build_event
from shared.shared.outbox_helpers import add_outbox_event
from shared.shared.crud_helpers import fetch_or_404, apply_partial_update

router = APIRouter()


def _to_response(u: User) -> UserResponse:
    return UserResponse(
        email=u.email,
        first_name=u.first_name,
        last_name=u.last_name,
        phone=u.phone,
        national_id=u.national_id,
        address_line=u.address_line,
        postal_code=u.postal_code,
        city=u.city,
        country=u.country,
        latitude=u.latitude,
        longitude=u.longitude,
        created_at=u.created_at,
    )


@router.post("/users", response_model=UserResponse)
async def create_user(data: CreateUser):
    async with SessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == data.email))
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
        db.add(u)

        add_outbox_event(db, OutboxEvent, build_event("user.created", data.model_dump()))

        add_outbox_event(db, OutboxEvent, evt)

        await db.commit()
        await db.refresh(u)
        return _to_response(u)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    async with SessionLocal() as db:
        res = await db.execute(select(User).order_by(User.id.asc()).limit(limit).offset(offset))
        rows = res.scalars().all()
        return [_to_response(u) for u in rows]


@router.get("/users/{email}", response_model=UserResponse)
async def get_user(email: str):
    async with SessionLocal() as db:
        u = await fetch_or_404(db, User, filter_column=User.email, filter_value=email, detail="User not found")
        return _to_response(u)


@router.put("/users/{email}/location", response_model=UserResponse)
async def update_user_location(email: str, data: UpdateUserLocation):
    async with SessionLocal() as db:
        u = await fetch_or_404(db, User, filter_column=User.email, filter_value=email, detail="User not found")

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

        add_outbox_event(db, OutboxEvent, evt)

        await db.commit()
        await db.refresh(u)
        return _to_response(u)


@router.put("/users/{email}", response_model=UserResponse)
async def update_user(email: str, data: UpdateUser):
    async with SessionLocal() as db:
        u = await fetch_or_404(db, User, filter_column=User.email, filter_value=email, detail="User not found")

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

        add_outbox_event(db, OutboxEvent, evt)

        await db.commit()
        await db.refresh(u)
        return _to_response(u)


@router.delete("/users/{email}")
async def delete_user(email: str):
    async with SessionLocal() as db:
        u = await fetch_or_404(db, User, filter_column=User.email, filter_value=email, detail="User not found")

        add_outbox_event(db, OutboxEvent, build_event("user.deleted", {"email": email}))

        await db.delete(u)
        await db.commit()
        return {"message": "deleted", "email": email}