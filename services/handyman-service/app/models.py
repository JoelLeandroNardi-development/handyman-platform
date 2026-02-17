from sqlalchemy import Column, Integer, String, JSON, Float
from .db import Base


class Handyman(Base):
    __tablename__ = "handymen"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    skills = Column(JSON, nullable=False)
    years_experience = Column(Integer, nullable=False)
    service_radius_km = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
