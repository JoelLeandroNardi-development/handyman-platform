from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared.schemas.auth import (
    AuthUserResponse, Login, Register, TokenResponse,
    UpdateAuthUser, UpdateAuthUserPassword, UpdateAuthUserRoles,
)
from shared.schemas.availability import AvailabilitySlot, OverlapRequest, SetAvailability
from shared.schemas.bookings import (
    BookingResponse, CancelBooking, CreateBooking, RejectBookingRequest,
)
from shared.schemas.handymen import (
    CreateHandyman, CreateHandymanReview, HandymanResponse,
    HandymanReviewResponse, InvalidHandymanSkillsItem,
    InvalidHandymanSkillsResponse, SkillCatalogCategoryItem,
    SkillCatalogFlatResponse, SkillCatalogPatchRequest,
    SkillCatalogReplaceRequest, SkillCatalogSkillItem,
    UpdateHandyman, UpdateLocation,
)
from shared.schemas.match import MatchLogResponse, MatchRequest, MatchResult, UpdateMatchLog
from shared.schemas.users import CreateUser, UpdateUser, UpdateUserLocation, UserResponse

@pytest.mark.unit
class TestAuthSchemas:
    def test_register_default_roles(self):
        p = Register(email="u@ex.com", password="secret123")
        assert p.roles == ["user"]

    def test_register_normalizes_roles(self):
        p = Register(email="u@ex.com", password="secret123", roles=["Admin", "user", "admin"])
        assert p.roles == ["admin", "user"]

    def test_login(self):
        assert Login(email="u@ex.com", password="s").email == "u@ex.com"

    def test_token_response(self):
        assert TokenResponse(access_token="jwt").access_token == "jwt"

    def test_auth_user_response(self):
        assert AuthUserResponse(id=1, email="u@ex.com", roles=["user"]).roles == ["user"]

    def test_update_password_min_length(self):
        with pytest.raises(ValidationError):
            UpdateAuthUserPassword(password="123")

    def test_update_roles_normalizes(self):
        p = UpdateAuthUserRoles(roles=["Handyman", "admin"])
        assert p.roles == ["handyman", "admin"]

    def test_update_auth_user_optional_roles(self):
        assert UpdateAuthUser(password="secret123").roles is None

    def test_update_auth_user_normalizes_roles(self):
        assert UpdateAuthUser(roles=["Admin", "user"]).roles == ["admin", "user"]

@pytest.mark.unit
class TestBookingSchemas:
    def test_create_booking_valid(self, sample_booking_data):
        p = CreateBooking(**sample_booking_data)
        assert p.desired_end > p.desired_start

    def test_create_booking_missing_required(self):
        with pytest.raises(ValidationError) as exc:
            CreateBooking(
                user_email="u@ex.com",
                handyman_email="h@ex.com",
                desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
            )
        assert "desired_start" in str(exc.value)

    @pytest.mark.parametrize("bad_start", ["not-a-date", "2026-13-45T25:61:61Z"])
    def test_create_booking_invalid_datetime(self, bad_start):
        with pytest.raises(ValidationError):
            CreateBooking(
                user_email="u@ex.com", handyman_email="h@ex.com",
                desired_start=bad_start, desired_end="2026-03-17T12:00:00Z",
                job_description="Fix faucet",
            )

    def test_create_booking_date_string_accepted(self):
        p = CreateBooking(
            user_email="u@ex.com", handyman_email="h@ex.com",
            desired_start="2026-03-17", desired_end="2026-03-17T12:00:00Z",
            job_description="Fix faucet",
        )
        assert p.desired_start.year == 2026

    def test_booking_response_defaults(self):
        r = BookingResponse(
            booking_id="b-1", status="PENDING",
            user_email="u@ex.com", handyman_email="h@ex.com",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )
        assert r.completed_by_user is False
        assert r.completed_by_handyman is False
        assert r.rejected_by_handyman is False
        assert r.completed_at is None

    def test_cancel_booking_default_reason(self):
        assert CancelBooking().reason == "user_requested"

    def test_reject_booking_requires_reason(self):
        with pytest.raises(ValidationError):
            RejectBookingRequest(reason="")

@pytest.mark.unit
class TestAvailabilitySchemas:
    def test_slot_schema(self):
        s = AvailabilitySlot(start="2026-03-17T10:00:00Z", end="2026-03-17T12:00:00Z")
        assert s.start.endswith("Z")

    def test_set_availability_empty_default(self):
        assert SetAvailability().slots == []

    def test_overlap_request_requires_values(self):
        with pytest.raises(ValidationError):
            OverlapRequest(desired_start="", desired_end="2026-03-17T12:00:00Z")

@pytest.mark.unit
class TestMatchSchemas:
    def test_match_request_parses(self):
        p = MatchRequest(
            latitude=45.0, longitude=9.0, skill="plumbing",
            desired_start="2026-03-17T10:00:00Z",
            desired_end="2026-03-17T12:00:00Z",
        )
        assert p.desired_end > p.desired_start

    def test_match_result_defaults(self):
        r = MatchResult(
            email="p@ex.com", latitude=45.0, longitude=9.0,
            distance_km=3.5, years_experience=8,
        )
        assert r.availability_unknown is False
        assert r.avg_rating == 0
        assert r.completed_jobs_count == 0

    def test_match_result_with_reputation(self):
        r = MatchResult(
            email="p@ex.com", latitude=45.0, longitude=9.0,
            distance_km=3.5, years_experience=8,
            avg_rating=4.7, rating_count=15,
            profile_completeness=88, completed_jobs_count=12,
        )
        assert r.avg_rating == 4.7 and r.completed_jobs_count == 12

    def test_match_log_response(self):
        assert MatchLogResponse(id=1, user_latitude=1.0, user_longitude=2.0, skill="plumbing").skill == "plumbing"

    def test_update_match_log_partial(self):
        p = UpdateMatchLog(skill="electrical")
        assert p.skill == "electrical" and p.user_latitude is None

@pytest.mark.unit
class TestUserSchemas:
    def test_create_user(self):
        p = CreateUser(email="u@ex.com", first_name="Joel")
        assert p.email == "u@ex.com"

    def test_update_location(self):
        assert UpdateUserLocation(latitude=10.0, longitude=20.0).latitude == 10.0

    def test_update_user_partial(self):
        p = UpdateUser(city="Milan")
        assert p.city == "Milan" and p.country is None

    def test_user_response(self):
        r = UserResponse(
            email="u@ex.com",
            created_at=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
        )
        assert r.created_at.year == 2026

@pytest.mark.unit
class TestHandymanSchemas:
    def test_create_handyman(self):
        assert CreateHandyman(
            email="p@ex.com", skills=["plumbing"],
            years_experience=5, service_radius_km=20,
        ).skills == ["plumbing"]

    def test_update_location(self):
        assert UpdateLocation(latitude=1.0, longitude=2.0).longitude == 2.0

    def test_update_partial(self):
        assert UpdateHandyman(service_radius_km=30).service_radius_km == 30

    def test_response_defaults(self):
        r = HandymanResponse(
            email="p@ex.com", skills=["plumbing"],
            years_experience=5, service_radius_km=20,
            created_at=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
        )
        assert r.avg_rating == 0 and r.rating_count == 0

    def test_skill_catalog_defaults(self):
        assert SkillCatalogReplaceRequest().catalog == {}
        assert SkillCatalogPatchRequest().upserts == {}

    def test_skill_catalog_response(self):
        skill = SkillCatalogSkillItem(key="plumbing", label="Plumbing", active=True, sort_order=1)
        cat = SkillCatalogCategoryItem(key="home", label="Home", active=True, sort_order=1, skills=[skill])
        resp = SkillCatalogFlatResponse(categories=[cat], allowed_skill_keys=["plumbing"])
        assert resp.categories[0].skills[0].key == "plumbing"

    def test_invalid_skills_response(self):
        item = InvalidHandymanSkillsItem(
            email="p@ex.com", current_skills=["foo"],
            invalid_skills=["foo"], valid_skills=["plumbing"],
        )
        assert InvalidHandymanSkillsResponse(items=[item], count=1).count == 1

    def test_review_rating_bounds(self):
        with pytest.raises(ValidationError):
            CreateHandymanReview(
                booking_id="b1", handyman_email="p@ex.com",
                user_email="u@ex.com", rating=0,
            )

    def test_review_response(self):
        r = HandymanReviewResponse(
            id=1, booking_id="b1", handyman_email="p@ex.com",
            user_email="u@ex.com", rating=5,
            created_at=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
        )
        assert r.rating == 5