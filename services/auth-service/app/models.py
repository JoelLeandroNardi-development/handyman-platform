from sqlalchemy import Column, Integer, String, JSON
from .db import Base


class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    roles = Column(JSON, nullable=False)
