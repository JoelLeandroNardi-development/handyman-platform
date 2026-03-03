from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func

from .db import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    booking_id = Column(String, unique=True, nullable=False, index=True)

    user_email = Column(String, nullable=False)
    handyman_email = Column(String, nullable=False)

    desired_start = Column(DateTime(timezone=True), nullable=False)
    desired_end = Column(DateTime(timezone=True), nullable=False)

    status = Column(String, nullable=False, default="PENDING")
    failure_reason = Column(String, nullable=True)

    canceled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True)

    # globally unique id for idempotency downstream
    event_id = Column(String, unique=True, nullable=False, index=True)

    event_type = Column(String, nullable=False, index=True)
    routing_key = Column(String, nullable=False, index=True)

    payload = Column(JSON, nullable=False)

    status = Column(String, nullable=False, default="PENDING")  # PENDING|SENT|FAILED
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)