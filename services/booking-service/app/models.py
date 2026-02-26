from sqlalchemy import Column, Integer, String, DateTime
from .db import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    booking_id = Column(String, unique=True, nullable=False, index=True)

    user_email = Column(String, nullable=False, index=True)
    handyman_email = Column(String, nullable=False, index=True)

    desired_start = Column(DateTime(timezone=True), nullable=False)
    desired_end = Column(DateTime(timezone=True), nullable=False)

    status = Column(String, nullable=False, index=True)  # PENDING/RESERVED/CONFIRMED/FAILED/EXPIRED
    failure_reason = Column(String, nullable=True)