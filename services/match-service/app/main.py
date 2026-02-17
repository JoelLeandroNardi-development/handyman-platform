import os
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.functions import ST_Distance
from shapely.geometry import Point
from geoalchemy2.shape import from_shape
from shared.database import get_engine, get_session
from shared.redis import redis_client
from .scoring import score
from handyman_service.models import Handyman

DATABASE_URL = os.getenv("HANDYMAN_DATABASE_URL")

engine = get_engine(DATABASE_URL)
SessionLocal = get_session(engine)

app = FastAPI()

@app.get("/match")
async def match(lat: float, lng: float, skill: str):
    async with SessionLocal() as db:
        user_point = from_shape(Point(lng, lat), srid=4326)

        result = await db.execute(
            select(
                Handyman,
                ST_Distance(Handyman.location, user_point).label("distance")
            )
        )

        candidates = result.all()

        ranked = []

        for handyman, distance in candidates:
            available = await redis_client.exists(f"availability:{handyman.id}")
            skill_overlap = 1 if skill in handyman.skills else 0
            final_score = score(
                distance / 1000,
                skill_overlap,
                handyman.rating,
                handyman.jobs_completed,
                available
            )
            ranked.append((handyman.id, final_score))

        ranked.sort(key=lambda x: x[1], reverse=True)

        return {"matches": ranked[:5]}
