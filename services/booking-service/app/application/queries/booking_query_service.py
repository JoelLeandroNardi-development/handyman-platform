from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..mappers import to_response
from ...domain.models import Booking
from ...domain.schemas import BookingResponse, CompletedJobsCountResponse
from ...infrastructure.repository import get_completed_jobs_count
from shared.core.db.crud import fetch_or_404

class BookingQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_booking(self, booking_id: str) -> BookingResponse:
        booking = await fetch_or_404(self.db, Booking, filter_column=Booking.booking_id, filter_value=booking_id, detail="Booking not found")
        return to_response(booking)

    async def list_bookings(
        self,
        limit: int,
        offset: int = 0,
        status: str | None = None,
        user_email: str | None = None,
        handyman_email: str | None = None,
    ) -> list[BookingResponse]:
        stmt = select(Booking).order_by(Booking.created_at.desc()).limit(limit).offset(offset)

        if status:
            stmt = stmt.where(Booking.status == status)
        if user_email:
            stmt = stmt.where(Booking.user_email == user_email)
        if handyman_email:
            stmt = stmt.where(Booking.handyman_email == handyman_email)

        res = await self.db.execute(stmt)
        rows = res.scalars().all()
        return [to_response(b) for b in rows]

    async def completed_count_for_handyman(self, handyman_email: str) -> CompletedJobsCountResponse:
        count = await get_completed_jobs_count(self.db, handyman_email)
        return {"handyman_email": handyman_email, "completed_jobs_count": count}