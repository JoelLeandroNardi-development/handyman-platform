from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared.shared import events as events_module
from shared.shared.db import create_db, make_get_db
from shared.shared.schemas.auth import (
    AuthUserResponse,
    Login,
    Register,
    TokenResponse,
    UpdateAuthUser,
    UpdateAuthUserPassword,
    UpdateAuthUserRoles,
)
from shared.shared.schemas.availability import AvailabilitySlot, OverlapRequest, SetAvailability
from shared.shared.schemas.handymen import (
    CreateHandyman,
    CreateHandymanReview,
    HandymanResponse,
    HandymanReviewResponse,
    InvalidHandymanSkillsItem,
    InvalidHandymanSkillsResponse,
    SkillCatalogCategoryItem,
    SkillCatalogFlatResponse,
    SkillCatalogPatchRequest,
    SkillCatalogReplaceRequest,
    SkillCatalogSkillItem,
    UpdateHandyman,
    UpdateLocation,
)
from shared.shared.schemas.match import MatchLogResponse, MatchRequest, MatchResult, UpdateMatchLog
from shared.shared.schemas.users import CreateUser, UpdateUser, UpdateUserLocation, UserResponse


@pytest.mark.unit
class TestAuthSchemas:

    def test_register_normalizes_default_roles(self):
        payload = Register(email="user@example.com", password="secret123")

        assert payload.roles == ["user"]

    def test_register_normalizes_custom_roles(self):
        payload = Register(email="user@example.com", password="secret123", roles=["Admin", "user", "admin"])

        assert payload.roles == ["admin", "user"]

    def test_login_schema(self):
        payload = Login(email="user@example.com", password="secret123")

        assert payload.email == "user@example.com"

    def test_token_response_schema(self):
        payload = TokenResponse(access_token="jwt-token")

        assert payload.access_token == "jwt-token"

    def test_auth_user_response_schema(self):
        payload = AuthUserResponse(id=1, email="user@example.com", roles=["user"])

        assert payload.roles == ["user"]

    def test_update_auth_user_password_min_length(self):
        with pytest.raises(ValidationError):
            UpdateAuthUserPassword(password="123")

    def test_update_auth_user_roles_normalizes(self):
        payload = UpdateAuthUserRoles(roles=["Handyman", "admin"])

        assert payload.roles == ["handyman", "admin"]

    def test_update_auth_user_leaves_roles_none(self):
        payload = UpdateAuthUser(password="secret123")

        assert payload.roles is None

    def test_update_auth_user_normalizes_roles(self):
        payload = UpdateAuthUser(roles=["Admin", "user"])

        assert payload.roles == ["admin", "user"]


@pytest.mark.unit
class TestAvailabilitySchemas:

    def test_availability_slot_schema(self):
        payload = AvailabilitySlot(start="2026-03-17T10:00:00Z", end="2026-03-17T12:00:00Z")

        assert payload.start.endswith("Z")

    def test_set_availability_defaults_empty(self):
        payload = SetAvailability()

        assert payload.slots == []

    def test_overlap_request_requires_values(self):
        with pytest.raises(ValidationError):
            OverlapRequest(desired_start="", desired_end="2026-03-17T12:00:00Z")


@pytest.mark.unit
class TestMatchSchemas:

    def test_match_request_parses_datetimes(self):
        payload = MatchRequest(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start="2026-03-17T10:00:00Z",
            desired_end="2026-03-17T12:00:00Z",
        )

        assert payload.desired_end > payload.desired_start

    def test_match_result_defaults(self):
        payload = MatchResult(
            email="pro@example.com",
            latitude=45.0,
            longitude=9.0,
            distance_km=3.5,
            years_experience=8,
        )

        assert payload.availability_unknown is False

    def test_match_log_response_schema(self):
        payload = MatchLogResponse(id=1, user_latitude=1.0, user_longitude=2.0, skill="plumbing")

        assert payload.skill == "plumbing"

    def test_update_match_log_partial(self):
        payload = UpdateMatchLog(skill="electrical")

        assert payload.skill == "electrical"
        assert payload.user_latitude is None


@pytest.mark.unit
class TestUserSchemas:

    def test_create_user_schema(self):
        payload = CreateUser(email="user@example.com", first_name="Joel")

        assert payload.email == "user@example.com"
        assert payload.first_name == "Joel"

    def test_update_user_location_schema(self):
        payload = UpdateUserLocation(latitude=10.0, longitude=20.0)

        assert payload.latitude == 10.0

    def test_update_user_partial_schema(self):
        payload = UpdateUser(city="Milan")

        assert payload.city == "Milan"
        assert payload.country is None

    def test_user_response_schema(self):
        payload = UserResponse(
            email="user@example.com",
            created_at=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
        )

        assert payload.created_at.year == 2026


@pytest.mark.unit
class TestHandymanSchemas:

    def test_create_handyman_schema(self):
        payload = CreateHandyman(
            email="pro@example.com",
            skills=["plumbing"],
            years_experience=5,
            service_radius_km=20,
        )

        assert payload.skills == ["plumbing"]

    def test_update_location_schema(self):
        payload = UpdateLocation(latitude=1.0, longitude=2.0)

        assert payload.longitude == 2.0

    def test_update_handyman_partial_schema(self):
        payload = UpdateHandyman(service_radius_km=30)

        assert payload.service_radius_km == 30

    def test_handyman_response_defaults(self):
        payload = HandymanResponse(
            email="pro@example.com",
            skills=["plumbing"],
            years_experience=5,
            service_radius_km=20,
            created_at=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
        )

        assert payload.avg_rating == 0
        assert payload.rating_count == 0

    def test_skill_catalog_request_defaults(self):
        replace_payload = SkillCatalogReplaceRequest()
        patch_payload = SkillCatalogPatchRequest()

        assert replace_payload.catalog == {}
        assert patch_payload.upserts == {}
        assert patch_payload.activate_skills == []

    def test_skill_catalog_response_schema(self):
        skill = SkillCatalogSkillItem(key="plumbing", label="Plumbing", active=True, sort_order=1)
        category = SkillCatalogCategoryItem(
            key="home",
            label="Home",
            active=True,
            sort_order=1,
            skills=[skill],
        )
        payload = SkillCatalogFlatResponse(categories=[category], allowed_skill_keys=["plumbing"])

        assert payload.categories[0].skills[0].key == "plumbing"

    def test_invalid_handyman_skills_response_schema(self):
        item = InvalidHandymanSkillsItem(
            email="pro@example.com",
            current_skills=["foo"],
            invalid_skills=["foo"],
            valid_skills=["plumbing"],
        )
        payload = InvalidHandymanSkillsResponse(items=[item], count=1)

        assert payload.count == 1

    def test_create_handyman_review_rating_bounds(self):
        with pytest.raises(ValidationError):
            CreateHandymanReview(
                booking_id="b1",
                handyman_email="pro@example.com",
                user_email="user@example.com",
                rating=0,
            )

    def test_handyman_review_response_schema(self):
        payload = HandymanReviewResponse(
            id=1,
            booking_id="b1",
            handyman_email="pro@example.com",
            user_email="user@example.com",
            rating=5,
            created_at=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
        )

        assert payload.rating == 5


@pytest.mark.unit
class TestSharedEventsAndDb:

    def test_utc_now_iso_returns_utc_string(self):
        value = events_module.utc_now_iso()

        assert "+00:00" in value or value.endswith("Z")

    def test_build_event_uses_defaults(self):
        event = events_module.build_event("booking.requested", {}, source="booking-service")

        assert event["event_type"] == "booking.requested"
        assert event["source"] == "booking-service"
        assert event["data"] == {}
        assert event["event_id"]

    def test_build_event_jsonable_falls_back_without_encoder(self, monkeypatch):
        monkeypatch.setattr(events_module, "_jsonable_encoder", None)

        event = events_module.build_event_jsonable(
            "booking.requested",
            {"when": datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc)},
            source="booking-service",
            event_id="evt-1",
            occurred_at="2026-03-17T10:00:00+00:00",
        )

        assert event["event_id"] == "evt-1"
        assert isinstance(event["data"]["when"], datetime)

    def test_make_event_builder_uses_service_name(self):
        builder = events_module.make_event_builder("booking-service")

        event = builder("booking.requested", {"booking_id": "b1"})

        assert event["source"] == "booking-service"

    def test_create_db_requires_environment_variable(self, monkeypatch):
        monkeypatch.delenv("TEST_DB_URL", raising=False)

        with pytest.raises(RuntimeError):
            create_db("TEST_DB_URL")

    def test_create_db_returns_engine_session_and_base(self, monkeypatch):
        monkeypatch.setenv("TEST_DB_URL", "sqlite+aiosqlite:///:memory:")

        engine, session_local, base = create_db("TEST_DB_URL", echo=False)

        assert engine is not None
        assert session_local is not None
        assert base is not None

    @pytest.mark.asyncio
    async def test_make_get_db_yields_session(self):
        session = object()

        class SessionCtx:
            async def __aenter__(self):
                return session

            async def __aexit__(self, exc_type, exc, tb):
                return False

        get_db = make_get_db(lambda: SessionCtx())

        yielded = []
        async for item in get_db():
            yielded.append(item)

        assert yielded == [session]