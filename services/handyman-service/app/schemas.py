from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CreateHandyman(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    skills: List[str]
    years_experience: int
    service_radius_km: int
    latitude: float | None = None
    longitude: float | None = None


class UpdateLocation(BaseModel):
    latitude: float
    longitude: float


class UpdateHandyman(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    skills: Optional[List[str]] = None
    years_experience: Optional[int] = None
    service_radius_km: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class HandymanResponse(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    skills: List[str]
    years_experience: int
    service_radius_km: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    avg_rating: float
    rating_count: int
    created_at: datetime


class SkillCatalogReplaceRequest(BaseModel):
    catalog: dict[str, List[str]] = Field(default_factory=dict)


class SkillCatalogPatchRequest(BaseModel):
    upserts: dict[str, List[str]] = Field(default_factory=dict)
    activate_skills: List[str] = Field(default_factory=list)
    deactivate_skills: List[str] = Field(default_factory=list)
    activate_categories: List[str] = Field(default_factory=list)
    deactivate_categories: List[str] = Field(default_factory=list)


class SkillCatalogSkillItem(BaseModel):
    key: str
    label: str
    active: bool
    sort_order: int


class SkillCatalogCategoryItem(BaseModel):
    key: str
    label: str
    active: bool
    sort_order: int
    skills: List[SkillCatalogSkillItem]


class SkillCatalogFlatResponse(BaseModel):
    categories: List[SkillCatalogCategoryItem]
    allowed_skill_keys: List[str]


class InvalidHandymanSkillsItem(BaseModel):
    email: str
    current_skills: List[str]
    invalid_skills: List[str]
    valid_skills: List[str]


class InvalidHandymanSkillsResponse(BaseModel):
    items: List[InvalidHandymanSkillsItem]
    count: int


class CreateHandymanReview(BaseModel):
    booking_id: str
    handyman_email: str
    user_email: str
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = Field(default=None, max_length=2000)


class HandymanReviewResponse(BaseModel):
    id: int
    booking_id: str
    handyman_email: str
    user_email: str
    rating: int
    review_text: Optional[str] = None
    created_at: datetime