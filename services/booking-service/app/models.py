from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from .db import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    booking_id = Column(String, unique=True, nullable=False, index=True)

    user_email = Column(String, nullable=False)
    handyman_email = Column(String, nullable=False)

    desired_start = Column(String, nullable=False)
    desired_end = Column(String, nullable=False)

    status = Column(String, nullable=False, default="PENDING")
    failure_reason = Column(String, nullable=True)

    canceled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)