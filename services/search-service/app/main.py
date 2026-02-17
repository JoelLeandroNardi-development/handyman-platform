import os
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.functions import ST_DWithin
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from shared.database import get_engine, get_session
from handyman_service.models import Handyman

DATABASE_URL = os.getenv("HANDYMAN_DATABASE_URL")

engine = get_engine(DATABASE_URL)
SessionLocal = get_session(engine)

app = FastAPI()

@app.get("/nearby")
async def nearby(lat: float, lng: float, radius_km: float):
    async with SessionLocal() as db:
        point = from_shape(Point(lng, lat), srid=4326)

        result = await db.execute(
            select(Handyman).where(
                ST_DWithin(Handyman.location, point, radius_km * 1000)
            )
        )

        return result.scalars().all()
