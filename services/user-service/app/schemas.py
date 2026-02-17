from pydantic import BaseModel


class CreateUser(BaseModel):
    email: str
    full_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class UpdateLocation(BaseModel):
    latitude: float
    longitude: float
