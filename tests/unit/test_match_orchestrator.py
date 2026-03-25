from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as redis_async

from tests.service_loader import load_service_app_module


@pytest.fixture
def match_orchestrator_module(monkeypatch):
    fake_redis = MagicMock()
    fake_redis.smembers = AsyncMock(return_value=set())
    fake_redis.delete = AsyncMock(return_value=0)
    fake_redis.pipeline = MagicMock()

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis_async, "from_url", lambda *args, **kwargs: fake_redis)

    module = load_service_app_module(
        "match-service",
        "match_orchestrator",
        package_name="match_orchestrator_test_app",
        reload_modules=True,
    )
    return module


@pytest.mark.unit
class TestRunMatchQuery:

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_blank_skill(self, match_orchestrator_module):
        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="   ",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_cached_result_when_available(self, match_orchestrator_module):
        cached_matches = [{"email": "pro@example.com", "distance_km": 1.5}]

        match_orchestrator_module.get_cached_result = AsyncMock(
            return_value=json.dumps(cached_matches)
        )
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert result == cached_matches

    @pytest.mark.asyncio
    async def test_ignores_corrupted_cache_and_computes_fresh(self, match_orchestrator_module):
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value="not-valid-json")
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[])
        match_orchestrator_module.set_cache_with_index = AsyncMock()

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert result == []
        match_orchestrator_module.get_effective_handymen_for_skill.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filters_candidates_outside_service_radius(self, match_orchestrator_module):
        handyman = {
            "email": "far@example.com",
            "latitude": 55.0,
            "longitude": 20.0,
            "service_radius_km": 5,
        }
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([handyman], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.set_cache_with_index = AsyncMock()

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_candidate_without_availability_in_strict_mode(self, match_orchestrator_module):
        handyman = {
            "email": "near@example.com",
            "latitude": 45.001,
            "longitude": 9.001,
            "service_radius_km": 50,
        }
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([handyman], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.get_effective_availability_slots = AsyncMock(return_value=(None, "missing"))
        match_orchestrator_module.set_cache_with_index = AsyncMock()

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_includes_candidate_with_unknown_availability_in_degraded_mode(self, match_orchestrator_module):
        handyman = {
            "email": "near@example.com",
            "latitude": 45.001,
            "longitude": 9.001,
            "service_radius_km": 50,
            "avg_rating": 4.5,
            "rating_count": 10,
            "profile_completeness": 0.8,
            "completed_jobs_count": 5,
            "years_experience": 3,
        }
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=False)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([handyman], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.get_effective_availability_slots = AsyncMock(return_value=(None, "missing"))
        match_orchestrator_module.set_cache_with_index = AsyncMock()

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert len(result) == 1
        assert result[0]["email"] == "near@example.com"
        assert result[0]["availability_unknown"] is True

    @pytest.mark.asyncio
    async def test_filters_candidate_with_non_overlapping_slots(self, match_orchestrator_module):
        handyman = {
            "email": "near@example.com",
            "latitude": 45.001,
            "longitude": 9.001,
            "service_radius_km": 50,
        }
        non_overlapping_slots = [
            {"start": "2026-03-17T14:00:00+00:00", "end": "2026-03-17T16:00:00+00:00"}
        ]
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([handyman], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.get_effective_availability_slots = AsyncMock(
            return_value=(non_overlapping_slots, "projection")
        )
        match_orchestrator_module.set_cache_with_index = AsyncMock()

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_ranked_match_for_available_candidate(self, match_orchestrator_module):
        handyman = {
            "email": "near@example.com",
            "latitude": 45.001,
            "longitude": 9.001,
            "service_radius_km": 50,
            "avg_rating": 4.5,
            "rating_count": 10,
            "profile_completeness": 0.8,
            "completed_jobs_count": 5,
            "years_experience": 3,
        }
        overlapping_slots = [
            {"start": "2026-03-17T09:00:00+00:00", "end": "2026-03-17T13:00:00+00:00"}
        ]
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([handyman], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.get_effective_availability_slots = AsyncMock(
            return_value=(overlapping_slots, "projection")
        )
        match_orchestrator_module.set_cache_with_index = AsyncMock()

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        assert len(result) == 1
        assert result[0]["email"] == "near@example.com"
        assert result[0]["availability_unknown"] is False
        assert result[0]["availability_source"] == "projection"

    @pytest.mark.asyncio
    async def test_writes_to_cache_when_results_found(self, match_orchestrator_module):
        handyman = {
            "email": "near@example.com",
            "latitude": 45.001,
            "longitude": 9.001,
            "service_radius_km": 50,
            "avg_rating": 0,
            "rating_count": 0,
            "profile_completeness": 0,
            "completed_jobs_count": 0,
            "years_experience": 0,
        }
        overlapping_slots = [
            {"start": "2026-03-17T09:00:00+00:00", "end": "2026-03-17T13:00:00+00:00"}
        ]
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([handyman], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.get_effective_availability_slots = AsyncMock(
            return_value=(overlapping_slots, "projection")
        )
        mock_cache_write = AsyncMock()
        match_orchestrator_module.set_cache_with_index = mock_cache_write

        await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        mock_cache_write.assert_awaited_once()
        call_kwargs = mock_cache_write.call_args.kwargs
        assert call_kwargs["mode"] == "strict"
        assert call_kwargs["ttl_seconds"] == 60
        assert call_kwargs["skill"] == "plumbing"

    @pytest.mark.asyncio
    async def test_skips_cache_write_when_no_results(self, match_orchestrator_module):
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[])
        mock_cache_write = AsyncMock()
        match_orchestrator_module.set_cache_with_index = mock_cache_write

        await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        mock_cache_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uses_degraded_ttl_when_no_availability_projections(self, match_orchestrator_module):
        handyman = {
            "email": "near@example.com",
            "latitude": 45.001,
            "longitude": 9.001,
            "service_radius_km": 50,
            "avg_rating": 0,
            "rating_count": 0,
            "profile_completeness": 0,
            "completed_jobs_count": 0,
            "years_experience": 0,
        }
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=False)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        match_orchestrator_module.get_effective_handymen_for_skill = AsyncMock(return_value=([handyman], "projection"))
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.get_effective_availability_slots = AsyncMock(return_value=(None, "missing"))
        mock_cache_write = AsyncMock()
        match_orchestrator_module.set_cache_with_index = mock_cache_write

        await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        mock_cache_write.assert_awaited_once()
        call_kwargs = mock_cache_write.call_args.kwargs
        assert call_kwargs["mode"] == "degraded"
        assert call_kwargs["ttl_seconds"] == 15

    @pytest.mark.asyncio
    async def test_uses_projected_handymen_when_available(self, match_orchestrator_module):
        """Projection-first: when projections exist, live fetch must not be called."""
        handyman = {
            "email": "proj@example.com",
            "latitude": 45.001,
            "longitude": 9.001,
            "service_radius_km": 50,
            "avg_rating": 4.0,
            "rating_count": 5,
            "profile_completeness": 0.9,
            "completed_jobs_count": 3,
            "years_experience": 2,
        }
        overlapping_slots = [
            {"start": "2026-03-17T09:00:00+00:00", "end": "2026-03-17T13:00:00+00:00"}
        ]
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        # get_effective_handymen_for_skill returns projection source — no live fetch needed
        mock_effective = AsyncMock(return_value=([handyman], "projection"))
        match_orchestrator_module.get_effective_handymen_for_skill = mock_effective
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.get_effective_availability_slots = AsyncMock(
            return_value=(overlapping_slots, "projection")
        )
        match_orchestrator_module.set_cache_with_index = AsyncMock()

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        mock_effective.assert_awaited_once_with("plumbing")
        assert len(result) == 1
        assert result[0]["email"] == "proj@example.com"

    @pytest.mark.asyncio
    async def test_falls_back_to_live_when_projections_empty(self, match_orchestrator_module):
        """Fallback path: when projections are empty, live source is used."""
        handyman = {
            "email": "live@example.com",
            "latitude": 45.001,
            "longitude": 9.001,
            "service_radius_km": 50,
            "avg_rating": 3.0,
            "rating_count": 2,
            "profile_completeness": 0.5,
            "completed_jobs_count": 1,
            "years_experience": 1,
        }
        overlapping_slots = [
            {"start": "2026-03-17T09:00:00+00:00", "end": "2026-03-17T13:00:00+00:00"}
        ]
        match_orchestrator_module.projections_have_any_availability = AsyncMock(return_value=True)
        match_orchestrator_module.get_cached_result = AsyncMock(return_value=None)
        # get_effective_handymen_for_skill signals fallback via "live" source label
        mock_effective = AsyncMock(return_value=([handyman], "live"))
        match_orchestrator_module.get_effective_handymen_for_skill = mock_effective
        match_orchestrator_module.hydrate_completed_jobs_counts = AsyncMock(return_value=[handyman])
        match_orchestrator_module.get_effective_availability_slots = AsyncMock(
            return_value=(overlapping_slots, "projection")
        )
        match_orchestrator_module.set_cache_with_index = AsyncMock()

        result = await match_orchestrator_module.run_match_query(
            latitude=45.0,
            longitude=9.0,
            skill="plumbing",
            desired_start=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
            desired_end=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
        )

        mock_effective.assert_awaited_once_with("plumbing")
        assert len(result) == 1
        assert result[0]["email"] == "live@example.com"
