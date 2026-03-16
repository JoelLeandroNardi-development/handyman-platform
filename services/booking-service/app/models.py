from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.sql import func

from .db import Base
from shared.shared.outbox_model import make_outbox_event_model


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    booking_id = Column(String, unique=True, nullable=False, index=True)

    user_email = Column(String, nullable=False)
    handyman_email = Column(String, nullable=False)

    desired_start = Column(DateTime(timezone=True), nullable=False)
    desired_end = Column(DateTime(timezone=True), nullable=False)

    job_description = Column(String, nullable=True)

    status = Column(String, nullable=False, default="PENDING")
    failure_reason = Column(String, nullable=True)

    canceled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(String, nullable=True)

    completed_by_user = Column(Boolean, nullable=False, default=False)
    completed_by_handyman = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    rejected_by_handyman = Column(Boolean, nullable=False, default=False)
    rejection_reason = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


OutboxEvent = make_outbox_event_model(Base)