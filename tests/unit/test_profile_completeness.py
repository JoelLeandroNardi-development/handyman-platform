"""Tests for handyman-service profile_completeness computation.

Covers:
  - fully complete profile  → 100
  - partially filled profile → proportional score
  - minimal / empty profile  → 0
  - edge cases around the city/country and lat/lng pair rules
"""
from __future__ import annotations

import pytest

from tests.service_loader import load_service_app_module


@pytest.fixture(scope="module")
def pc_module():
    """Load the profile_completeness module from handyman-service (domain/)."""
    return load_service_app_module(
        "handyman-service",
        "domain/profile_policies",
        package_name="handyman_pc_test_app",
    )


def _full_profile() -> dict:
    """Return kwargs representing a fully complete handyman profile."""
    return dict(
        first_name="Jane",
        last_name="Doe",
        phone="+1234567890",
        city="Lima",
        country="Peru",
        skills=["plumbing"],
        years_experience=5,
        service_radius_km=20,
        latitude=-12.04,
        longitude=-77.03,
    )


@pytest.mark.unit
class TestProfileCompleteness:
    """Profile completeness scoring (0..100 integer)."""

    # ── full / empty extremes ──────────────────────────────────────────

    def test_fully_complete_profile_scores_100(self, pc_module):
        score = pc_module.compute_profile_completeness(**_full_profile())
        assert score == 100

    def test_minimal_empty_profile_scores_0(self, pc_module):
        score = pc_module.compute_profile_completeness(
            skills=[],
            years_experience=0,
            service_radius_km=0,
        )
        assert score == 0

    def test_all_none_defaults_score_0(self, pc_module):
        score = pc_module.compute_profile_completeness()
        assert score == 0

    # ── partial profiles ───────────────────────────────────────────────

    def test_only_names_filled(self, pc_module):
        """first_name + last_name = 2/8 checks → 25."""
        score = pc_module.compute_profile_completeness(
            first_name="Jane",
            last_name="Doe",
        )
        assert score == 25

    def test_half_filled_profile(self, pc_module):
        """4 out of 8 checks → 50."""
        score = pc_module.compute_profile_completeness(
            first_name="Jane",
            last_name="Doe",
            phone="+123",
            city="Lima",
        )
        assert score == 50

    def test_everything_except_location(self, pc_module):
        """7/8 checks → 88."""
        profile = _full_profile()
        profile["latitude"] = None
        profile["longitude"] = None
        score = pc_module.compute_profile_completeness(**profile)
        assert score == 88

    # ── city/country pair rule ─────────────────────────────────────────

    def test_city_alone_counts(self, pc_module):
        score = pc_module.compute_profile_completeness(city="Lima")
        # 1 check out of 8 → round(12.5) = 12
        assert score == 12

    def test_country_alone_counts(self, pc_module):
        score = pc_module.compute_profile_completeness(country="Peru")
        assert score == 12

    def test_city_and_country_still_one_check(self, pc_module):
        """city + country together is still a single check, same as city alone."""
        score_both = pc_module.compute_profile_completeness(city="Lima", country="Peru")
        score_city = pc_module.compute_profile_completeness(city="Lima")
        assert score_both == score_city

    # ── lat/lng pair rule ──────────────────────────────────────────────

    def test_latitude_only_does_not_count(self, pc_module):
        score = pc_module.compute_profile_completeness(latitude=-12.04)
        assert score == 0

    def test_longitude_only_does_not_count(self, pc_module):
        score = pc_module.compute_profile_completeness(longitude=-77.03)
        assert score == 0

    def test_both_lat_lng_counts(self, pc_module):
        score = pc_module.compute_profile_completeness(latitude=-12.04, longitude=-77.03)
        assert score == 12

    # ── skills edge cases ──────────────────────────────────────────────

    def test_empty_skills_list_does_not_count(self, pc_module):
        score = pc_module.compute_profile_completeness(skills=[])
        assert score == 0

    def test_one_skill_counts(self, pc_module):
        score = pc_module.compute_profile_completeness(skills=["plumbing"])
        assert score == 12

    def test_multiple_skills_still_one_check(self, pc_module):
        score_one = pc_module.compute_profile_completeness(skills=["plumbing"])
        score_many = pc_module.compute_profile_completeness(skills=["plumbing", "electrical"])
        assert score_one == score_many

    # ── numeric edge cases ─────────────────────────────────────────────

    def test_zero_experience_does_not_count(self, pc_module):
        score = pc_module.compute_profile_completeness(years_experience=0)
        assert score == 0

    def test_positive_experience_counts(self, pc_module):
        score = pc_module.compute_profile_completeness(years_experience=1)
        assert score == 12

    def test_zero_radius_does_not_count(self, pc_module):
        score = pc_module.compute_profile_completeness(service_radius_km=0)
        assert score == 0

    # ── return type ────────────────────────────────────────────────────

    def test_return_type_is_int(self, pc_module):
        score = pc_module.compute_profile_completeness(**_full_profile())
        assert isinstance(score, int)

    def test_score_within_bounds(self, pc_module):
        for kwargs in [
            {},
            _full_profile(),
            dict(first_name="X"),
            dict(skills=["a"], years_experience=3, service_radius_km=10),
        ]:
            score = pc_module.compute_profile_completeness(**kwargs)
            assert 0 <= score <= 100
