from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

_ALLOWED_ROLES = {"user", "handyman", "admin"}


class Register(BaseModel):
    email: str
    password: str
    roles: List[str] = Field(default_factory=lambda: ["user"])

    def model_post_init(self, __context):
        normalized = []
        for r in self.roles:
            rr = (r or "").strip().lower()
            if rr not in _ALLOWED_ROLES:
                raise ValueError(f"Invalid role: {r}. Allowed: {sorted(_ALLOWED_ROLES)}")
            if rr not in normalized:
                normalized.append(rr)
        if not normalized:
            normalized = ["user"]
        object.__setattr__(self, "roles", normalized)


class Login(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str


class AuthUserResponse(BaseModel):
    id: int
    email: str
    roles: List[str]


class UpdateAuthUser(BaseModel):
    password: Optional[str] = Field(default=None, min_length=6)
    roles: Optional[List[str]] = None

    def model_post_init(self, __context):
        if self.roles is None:
            return
        normalized = []
        for r in self.roles:
            rr = (r or "").strip().lower()
            if rr not in _ALLOWED_ROLES:
                raise ValueError(f"Invalid role: {r}. Allowed: {sorted(_ALLOWED_ROLES)}")
            if rr not in normalized:
                normalized.append(rr)
        if not normalized:
            raise ValueError("roles must not be empty")
        object.__setattr__(self, "roles", normalized)


class CreateUser(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UpdateUserLocation(BaseModel):
    latitude: float
    longitude: float


class UpdateUser(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UserResponse(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime


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
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UpdateHandymanLocation(BaseModel):
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
    avg_rating: float = 0
    rating_count: int = 0
    created_at: datetime


class OnboardingUserRequest(BaseModel):
    email: str
    password: str
    roles: List[str] = Field(default_factory=lambda: ["user"])
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class OnboardingHandymanRequest(BaseModel):
    email: str
    password: str
    roles: List[str] = Field(default_factory=lambda: ["handyman"])
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


class OnboardingCombinedRequest(BaseModel):
    email: str
    password: str
    roles: List[str] = Field(default_factory=lambda: ["user", "handyman"])

    user_profile: CreateUser
    handyman_profile: CreateHandyman


class OnboardingUserResponse(BaseModel):
    auth_user: AuthUserResponse
    user_profile: UserResponse


class OnboardingHandymanResponse(BaseModel):
    auth_user: AuthUserResponse
    handyman_profile: HandymanResponse


class OnboardingCombinedResponse(BaseModel):
    auth_user: AuthUserResponse
    user_profile: UserResponse
    handyman_profile: HandymanResponse


class SkillCatalogReplaceRequest(BaseModel):
    catalog: dict[str, List[str]]


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


class AvailabilitySlot(BaseModel):
    start: str
    end: str


class SetAvailability(BaseModel):
    slots: List[AvailabilitySlot]


class MatchRequest(BaseModel):
    latitude: float
    longitude: float
    skill: str
    job_description: Optional[str] = None
    desired_start: datetime
    desired_end: datetime


class MatchResult(BaseModel):
    email: str
    latitude: float
    longitude: float
    distance_km: float
    years_experience: int
    availability_unknown: bool = False


class CreateBookingRequest(BaseModel):
    user_email: str
    handyman_email: str
    desired_start: datetime
    desired_end: datetime
    job_description: Optional[str] = None


class BookingResponse(BaseModel):
    booking_id: str
    status: str
    user_email: str
    handyman_email: str
    desired_start: datetime
    desired_end: datetime
    job_description: Optional[str] = None
    completed_by_user: bool = False
    completed_by_handyman: bool = False
    completed_at: Optional[datetime] = None
    completion_rejected_by_handyman: bool = False
    completion_rejection_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None


class ConfirmBookingResponse(BaseModel):
    booking_id: str
    status: str


class CancelBookingRequest(BaseModel):
    reason: Optional[str] = "user_requested"


class CancelBookingResponse(BaseModel):
    booking_id: str
    status: str
    cancellation_reason: Optional[str] = None


class CompleteBookingResponse(BaseModel):
    booking_id: str
    status: str
    completed_by_user: bool
    completed_by_handyman: bool
    completed_at: Optional[datetime] = None


class RejectCompletionRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class RejectCompletionResponse(BaseModel):
    booking_id: str
    status: str
    completion_rejected_by_handyman: bool
    completion_rejection_reason: Optional[str] = None
    completed_by_user: bool = False
    completed_by_handyman: bool = False


class UpdateBookingAdmin(BaseModel):
    status: Optional[str] = None
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    job_description: Optional[str] = None


class MeResponse(BaseModel):
    email: str
    roles: List[str]
    user_profile: Optional[UserResponse] = None
    handyman_profile: Optional[HandymanResponse] = None