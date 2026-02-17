import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import jwt

from .db import SessionLocal
from .models import AuthUser
from .schemas import Register, Login

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"])

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")


async def get_db():
    async with SessionLocal() as session:
        yield session


@router.post("/register")
async def register(data: Register, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuthUser).where(AuthUser.email == data.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    hashed = pwd_context.hash(data.password)

    user = AuthUser(email=data.email, password=hashed)
    db.add(user)
    await db.commit()

    return {"message": "User registered"}


@router.post("/login")
async def login(data: Login, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuthUser).where(AuthUser.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not pwd_context.verify(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode(
        {"sub": user.email},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    return {"access_token": token}
