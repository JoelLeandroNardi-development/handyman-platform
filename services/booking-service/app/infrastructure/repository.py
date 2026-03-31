from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.models import Booking

async def get_completed_jobs_count(db: AsyncSession, handyman_email: str) -> int:
    res = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.handyman_email == handyman_email,
            Booking.status == "COMPLETED",
        )
    )
    return res.scalar_one()

async def get_completed_jobs_counts(db: AsyncSession, handyman_emails: list[str]) -> dict[str, int]:
    if not handyman_emails:
        return {}

    unique_emails = list(set(handyman_emails))

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