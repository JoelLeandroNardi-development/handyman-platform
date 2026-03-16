import os
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from passlib.context import CryptContext
from jose import jwt

from .db import SessionLocal
from .models import AuthUser
from .schemas import Register, Login, AuthUserResponse, UpdateAuthUser
from shared.shared.crud_helpers import fetch_or_404

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"])

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM") or "HS256"

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")


async def get_db():
    async with SessionLocal() as session:
        yield session


def _to_response(u: AuthUser) -> AuthUserResponse:
    return AuthUserResponse(
        id=u.id,
        email=u.email,
        roles=list(u.roles or []),
    )


@router.post("/register")
async def register(data: Register, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuthUser).where(AuthUser.email == data.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    hashed = pwd_context.hash(data.password)

    user = AuthUser(
        email=data.email,
        password=hashed,
        roles=data.roles,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"message": "User registered", "roles": user.roles}


@router.post("/login")
async def login(data: Login, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuthUser).where(AuthUser.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not pwd_context.verify(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode(
        {
            "sub": user.email,
            "roles": user.roles,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    return {"access_token": token}


@router.get("/auth-users", response_model=list[AuthUserResponse])
async def list_auth_users(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(AuthUser).order_by(AuthUser.id.asc()).limit(limit).offset(offset)
    )
    rows = res.scalars().all()
    return [_to_response(u) for u in rows]


@router.get("/auth-users/{user_id}", response_model=AuthUserResponse)
async def get_auth_user(user_id: int, db: AsyncSession = Depends(get_db)):
    u = await fetch_or_404(db, AuthUser, filter_column=AuthUser.id, filter_value=user_id, detail="Auth user not found")
    return _to_response(u)


@router.get("/auth-users/by-email/{email}", response_model=AuthUserResponse)
async def get_auth_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    u = await fetch_or_404(db, AuthUser, filter_column=AuthUser.email, filter_value=email, detail="Auth user not found")
    return _to_response(u)


@router.put("/auth-users/{user_id}", response_model=AuthUserResponse)
async def update_auth_user(
    user_id: int,
    data: UpdateAuthUser,
    db: AsyncSession = Depends(get_db),
):
    u = await fetch_or_404(db, AuthUser, filter_column=AuthUser.id, filter_value=user_id, detail="Auth user not found")

    if data.password is not None:
        u.password = pwd_context.hash(data.password)

    if data.roles is not None:
        u.roles = data.roles

    await db.commit()
    await db.refresh(u)
    return _to_response(u)


@router.delete("/auth-users/{user_id}")
async def delete_auth_user(user_id: int, db: AsyncSession = Depends(get_db)):
    u = await fetch_or_404(db, AuthUser, filter_column=AuthUser.id, filter_value=user_id, detail="Auth user not found")

    await db.execute(delete(AuthUser).where(AuthUser.id == user_id))
    await db.commit()

    return {"message": "deleted", "user_id": user_id}