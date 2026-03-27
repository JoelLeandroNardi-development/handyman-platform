from __future__ import annotations

from sqlalchemy import select, func

from .models import Booking
from ..infrastructure.db import SessionLocal

async def get_completed_jobs_count(handyman_email: str) -> int:
    async with SessionLocal() as db:
        res = await db.execute(
            select(func.count(Booking.id)).where(
                Booking.handyman_email == handyman_email,
                Booking.status == "COMPLETED",
            )
        )
        return res.scalar_one()

async def get_completed_jobs_counts(handyman_emails: list[str]) -> dict[str, int]:
    if not handyman_emails:
        return {}

    unique_emails = list(set(handyman_emails))

    async with SessionLocal() as db:
        res = await db.execute(
            select(
                Booking.handyman_email,
                func.count(Booking.id),
            )
            .where(
                Booking.handyman_email.in_(unique_emails),
                Booking.status == "COMPLETED",
            )
            .group_by(Booking.handyman_email)
        )
        rows = {email: count for email, count in res.all()}

    return {email: rows.get(email, 0) for email in unique_emails}