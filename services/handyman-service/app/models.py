from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.sql import func

from .db import Base


class Handyman(Base):
    __tablename__ = "handymen"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)

    skills = Column(JSON, nullable=False)

    years_experience = Column(Integer, nullable=False)
    service_radius_km = Column(Integer, nullable=False)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True)

    event_id = Column(String, unique=True, nullable=False, index=True)

    event_type = Column(String, nullable=False, index=True)
    routing_key = Column(String, nullable=False, index=True)

    payload = Column(JSON, nullable=False)

    status = Column(String, nullable=False, default="PENDING")
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)