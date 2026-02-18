from sqlalchemy import Column, Integer, Float, String
from .db import Base


class MatchLog(Base):
    __tablename__ = "match_logs"

    id = Column(Integer, primary_key=True)
    user_latitude = Column(Float, nullable=False)
    user_longitude = Column(Float, nullable=False)
    skill = Column(String, nullable=False)
