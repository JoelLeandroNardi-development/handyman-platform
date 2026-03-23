"""Completed-jobs aggregate for handymen.

Provides completed_jobs_count keyed by handyman_email, derived from
bookings in the COMPLETED state.  Because the count is computed via a
live query against the bookings table, duplicate event delivery or
replayed state transitions cannot double-increment the count.

Scale: non-negative integer (0+).
"""

from __future__ import annotations

from sqlalchemy import select, func

from .db import SessionLocal
from .models import Booking


async def get_completed_jobs_count(handyman_email: str) -> int:
    """Return the number of COMPLETED bookings for a single handyman."""
    async with SessionLocal() as db:
        res = await db.execute(
            select(func.count(Booking.id)).where(
                Booking.handyman_email == handyman_email,
                Booking.status == "COMPLETED",
            )
        )
        return res.scalar_one()


async def get_completed_jobs_counts(handyman_emails: list[str]) -> dict[str, int]:
    """Return completed-booking counts for a batch of handyman emails.

    Returns a dict keyed by handyman_email.  Emails with zero completed
    bookings are included with a count of 0.
    """
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
