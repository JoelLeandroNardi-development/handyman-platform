from pydantic import BaseModel, Field
from typing import List, Optional
from shared.shared.schemas.auth import (
    Register,
    Login,
    GoogleLoginRequest,
    GoogleLoginResponse,
    TokenPairResponse,
    TokenResponse,
    RefreshRequest,
    LogoutRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    EmailVerifyRequest,
    EmailVerifyConfirmRequest,
    AuthActionResponse,
    AuthUserResponse,
    UpdateAuthUser,
)
from shared.shared.schemas.users import (
    CreateUser,
    UpdateUserLocation,
    UpdateUser,
    UserResponse,
)
from shared.shared.schemas.handymen import (
    CreateHandyman,
    UpdateLocation as UpdateHandymanLocation,
    UpdateHandyman,
    HandymanResponse,
    SkillCatalogReplaceRequest,
    SkillCatalogPatchRequest,
    SkillCatalogSkillItem,
    SkillCatalogCategoryItem,
    SkillCatalogFlatResponse,
    InvalidHandymanSkillsItem,
    InvalidHandymanSkillsResponse,
    HandymanReviewResponse,
)
from shared.shared.schemas.availability import (
    AvailabilitySlot,
    SetAvailability,
)
from shared.shared.schemas.match import (
    MatchRequest,
    MatchResult,
)
from shared.shared.schemas.bookings import (
    BookingResponse,
    ConfirmBookingResponse,
    CancelBookingResponse,
    CompleteBookingResponse,
    RejectBookingRequest,
    RejectBookingResponse,
    UpdateBookingAdmin,
)
from shared.shared.schemas.bookings import CreateBooking as CreateBookingRequest
from shared.shared.schemas.bookings import CancelBooking as CancelBookingRequest
from shared.shared.schemas.notifications import (
    MarkAllReadResponse,
    NotificationItem,
    NotificationListResponse,
    NotificationPreferencesResponse,
    PushDeviceResponse,
    RegisterPushDeviceRequest,
    UnreadCountResponse,
    UpdateNotificationPreferencesRequest,
)

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


class CreateHandymanReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = Field(default=None, max_length=2000)


class MeResponse(BaseModel):
    email: str
    roles: List[str]
    user_profile: Optional[UserResponse] = None
    handyman_profile: Optional[HandymanResponse] = None


class OkResponse(BaseModel):
    ok: bool = True
