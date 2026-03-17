from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as redis_async

from tests.service_loader import load_service_app_module


@pytest.fixture
def match_services_module(monkeypatch):
    fake_redis = MagicMock()
    fake_redis.smembers = AsyncMock(return_value=set())
    fake_redis.delete = AsyncMock(return_value=0)
    fake_redis.pipeline = MagicMock()

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis_async, "from_url", lambda *args, **kwargs: fake_redis)

    module = load_service_app_module(
        "match-service",
        "services",
        package_name="match_service_test_app",
        reload_modules=True,
    )
    module.redis_client = fake_redis
    return module


@pytest.mark.unit
class TestMatchServiceHelpers:

    def test_norm_lowercases_and_strips(self, match_services_module):
        assert match_services_module.norm("  Plumbing  ") == "plumbing"

    def test_parse_dt_normalizes_naive_datetime(self, match_services_module):
        naive = datetime(2026, 3, 17, 10, 0, 0)

        result = match_services_module.parse_dt(naive)

        assert result.tzinfo == timezone.utc

    def test_parse_dt_accepts_iso_string(self, match_services_module):
        result = match_services_module.parse_dt("2026-03-17T10:00:00-05:00")

        assert result.hour == 15
        assert result.tzinfo == timezone.utc

    def test_parse_dt_rejects_unsupported_type(self, match_services_module):
        with pytest.raises(ValueError):
            match_services_module.parse_dt(42)

    def test_haversine_zero_distance(self, match_services_module):
        assert match_services_module.haversine(45.0, 9.0, 45.0, 9.0) == 0

    def test_bucket_id_uses_grid(self, match_services_module):
        assert match_services_module.bucket_id(0.11, -0.11) == (2, -3)

    def test_time_bucket_uses_utc_normalization(self, match_services_module):
        dt = datetime(2026, 3, 17, 10, 7, tzinfo=timezone.utc)

        result = match_services_module.time_bucket(dt)

        assert result == int(dt.timestamp()) // match_services_module.TIME_BUCKET_SECONDS

    def test_cache_key_encodes_mode_bucket_and_skill(self, match_services_module):
        key = match_services_module.cache_key(
            0.11,
            -0.11,
            "plumbing",
            True,
            datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
        )

        assert key.startswith("match:degraded:plumbing:")
        assert "lat=2" in key
        assert "lon=-3" in key

    def test_km_to_deg_lon_clamps_near_poles(self, match_services_module):
        result = match_services_module.km_to_deg_lon(10, 89.999)

        assert result > 0
        assert result < 10

    def test_buckets_in_radius_includes_origin_bucket(self, match_services_module):
        buckets = match_services_module.buckets_in_radius(0.0, 0.0, 6)

        assert (0, 0) in buckets

    def test_normalize_handyman_deduplicates_skills(self, match_services_module):
        result = match_services_module._normalize_handyman(
            {
                "email": "pro@example.com",
                "skills": [" Plumbing ", "plumbing", "Electrical"],
                "years_experience": 8,
            }
        )

        assert result["email"] == "pro@example.com"
        assert result["skills"] == ["plumbing", "electrical"]
        assert result["years_experience"] == 8

    def test_projected_has_overlap_checks_slots(self, match_services_module):
        slots = [
            {
                "start": "2026-03-17T10:00:00+00:00",
                "end": "2026-03-17T12:00:00+00:00",
            }
        ]

        assert match_services_module.projected_has_overlap(
            slots,
            datetime(2026, 3, 17, 11, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 17, 11, 30, tzinfo=timezone.utc),
        ) is True


@pytest.mark.unit
class TestMatchServiceRedisFlows:

    @pytest.mark.asyncio
    async def test_invalidate_bucket_deletes_cached_keys_and_index(self, match_services_module):
        fake_pipe = MagicMock()
        fake_pipe.delete = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[2, 1])

        match_services_module.redis_client.smembers = AsyncMock(return_value={"cache:a", "cache:b"})
        match_services_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)

        deleted = await match_services_module.invalidate_bucket("strict", "Plumbing", 2, 3)

        assert deleted == 2
        first_delete_args = fake_pipe.delete.call_args_list[0].args
        assert set(first_delete_args) == {"cache:a", "cache:b"}
        fake_pipe.delete.assert_any_call("matchkeys:strict:plumbing:lat=2:lon=3")

    @pytest.mark.asyncio
    async def test_invalidate_bucket_deletes_empty_index_when_no_keys(self, match_services_module):
        match_services_module.redis_client.smembers = AsyncMock(return_value=set())
        match_services_module.redis_client.delete = AsyncMock(return_value=1)

        deleted = await match_services_module.invalidate_bucket("unknown", "Plumbing", 1, 2)

        assert deleted == 0
        match_services_module.redis_client.delete.assert_awaited_once_with(
            "matchkeys:strict:plumbing:lat=1:lon=2"
        )

    @pytest.mark.asyncio
    async def test_get_handyman_projection_returns_none_for_empty_email(self, match_services_module):
        result = await match_services_module.get_handyman_projection("")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_handyman_projection_returns_none_for_invalid_json(self, match_services_module):
        match_services_module.redis_client.get = AsyncMock(return_value="not-json")

        result = await match_services_module.get_handyman_projection("pro@example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_handyman_projection_updates_skill_indexes(self, match_services_module):
        fake_pipe = MagicMock()
        fake_pipe.set = MagicMock()
        fake_pipe.sadd = MagicMock()
        fake_pipe.srem = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[])
        match_services_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)
        match_services_module.get_handyman_projection = AsyncMock(
            return_value={"skills": ["plumbing", "painting"]}
        )

        await match_services_module.upsert_handyman_projection(
            {
                "email": "pro@example.com",
                "skills": ["plumbing", "electrical"],
                "latitude": 1,
                "longitude": 2,
            }
        )

        fake_pipe.srem.assert_called_once_with("proj:handymen:skill:painting", "pro@example.com")
        fake_pipe.sadd.assert_any_call("proj:handymen:skill:plumbing", "pro@example.com")
        fake_pipe.sadd.assert_any_call("proj:handymen:skill:electrical", "pro@example.com")

    @pytest.mark.asyncio
    async def test_delete_handyman_projection_removes_indexes(self, match_services_module):
        fake_pipe = MagicMock()
        fake_pipe.delete = MagicMock()
        fake_pipe.srem = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[])
        match_services_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)
        match_services_module.get_handyman_projection = AsyncMock(
            return_value={"skills": ["plumbing", "electrical"]}
        )

        deleted = await match_services_module.delete_handyman_projection("pro@example.com")

        assert deleted == {"skills": ["plumbing", "electrical"]}
        fake_pipe.delete.assert_called_once_with("proj:handyman:pro@example.com")
        fake_pipe.srem.assert_any_call("proj:handymen:index", "pro@example.com")
        fake_pipe.srem.assert_any_call("proj:handymen:skill:plumbing", "pro@example.com")
        fake_pipe.srem.assert_any_call("proj:handymen:skill:electrical", "pro@example.com")

    @pytest.mark.asyncio
    async def test_list_projected_handymen_by_skill_filters_bad_rows(self, match_services_module):
        fake_pipe = MagicMock()
        fake_pipe.get = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=['{"email":"a@example.com"}', None, 'not-json'])
        match_services_module.redis_client.smembers = AsyncMock(return_value={"a@example.com", "b@example.com", "c@example.com"})
        match_services_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)

        rows = await match_services_module.list_projected_handymen_by_skill(" Plumbing ")

        assert rows == [{"email": "a@example.com"}]

    @pytest.mark.asyncio
    async def test_upsert_availability_projection_deletes_when_no_valid_slots(self, match_services_module):
        match_services_module.delete_availability_projection = AsyncMock()

        await match_services_module.upsert_availability_projection(
            email="pro@example.com",
            slots=[{"start": "bad", "end": "worse"}],
        )

        match_services_module.delete_availability_projection.assert_awaited_once_with("pro@example.com")

    @pytest.mark.asyncio
    async def test_upsert_availability_projection_persists_clean_slots(self, match_services_module):
        fake_pipe = MagicMock()
        fake_pipe.set = MagicMock()
        fake_pipe.sadd = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[])
        match_services_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)

        await match_services_module.upsert_availability_projection(
            email="pro@example.com",
            slots=[
                {"start": "2026-03-17T10:00:00+00:00", "end": "2026-03-17T12:00:00+00:00"},
                {"start": "2026-03-17T12:00:00+00:00", "end": "2026-03-17T11:00:00+00:00"},
            ],
        )

        payload = fake_pipe.set.call_args.args[1]
        assert '"email": "pro@example.com"' in payload
        assert '2026-03-17T10:00:00+00:00' in payload

    @pytest.mark.asyncio
    async def test_get_availability_slots_handles_invalid_json(self, match_services_module):
        match_services_module.redis_client.get = AsyncMock(return_value="not-json")

        result = await match_services_module.get_availability_slots("pro@example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_effective_availability_slots_uses_projection_first(self, match_services_module):
        match_services_module.get_availability_slots = AsyncMock(return_value=[{"start": "s", "end": "e"}])

        slots, source = await match_services_module.get_effective_availability_slots("pro@example.com")

        assert source == "projection"
        assert slots == [{"start": "s", "end": "e"}]

    @pytest.mark.asyncio
    async def test_get_effective_availability_slots_fetches_live_and_caches(self, match_services_module):
        match_services_module.get_availability_slots = AsyncMock(return_value=None)
        match_services_module.fetch_availability_http = AsyncMock(return_value=[{"start": "s", "end": "e"}])
        match_services_module.upsert_availability_projection = AsyncMock()

        slots, source = await match_services_module.get_effective_availability_slots("pro@example.com")

        assert source == "live"
        assert slots == [{"start": "s", "end": "e"}]
        match_services_module.upsert_availability_projection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seed_handyman_projection_if_empty_bootstraps(self, match_services_module):
        match_services_module.handyman_projection_count = AsyncMock(return_value=0)
        match_services_module.fetch_handymen_http = AsyncMock(
            return_value=[{"email": "a@example.com"}, {"email": "b@example.com"}]
        )
        match_services_module.upsert_handyman_projection = AsyncMock(side_effect=[None, RuntimeError("bad")])

        result = await match_services_module.seed_handyman_projection_if_empty()

        assert result == {"seeded": True, "reason": "bootstrapped", "count": 1}

    @pytest.mark.asyncio
    async def test_get_live_handymen_for_skill_filters_and_caches(self, match_services_module):
        match_services_module.fetch_handymen_http = AsyncMock(
            return_value=[
                {"email": "a@example.com", "skills": ["plumbing", "electrical"]},
                {"email": "b@example.com", "skills": ["painting"]},
            ]
        )
        match_services_module.upsert_handyman_projection = AsyncMock()

        result = await match_services_module.get_live_handymen_for_skill("Plumbing")

        assert result == [{"email": "a@example.com", "skills": ["plumbing", "electrical"]}]
        match_services_module.upsert_handyman_projection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_effective_handymen_for_skill_prefers_projection(self, match_services_module):
        match_services_module.list_projected_handymen_by_skill = AsyncMock(return_value=[{"email": "a@example.com"}])

        handymen, source = await match_services_module.get_effective_handymen_for_skill("plumbing")

        assert handymen == [{"email": "a@example.com"}]
        assert source == "projection"

    @pytest.mark.asyncio
    async def test_set_cache_with_index_writes_cache_and_index(self, match_services_module):
        fake_pipe = MagicMock()
        fake_pipe.set = MagicMock()
        fake_pipe.sadd = MagicMock()
        fake_pipe.expire = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[])
        match_services_module.redis_client.pipeline = MagicMock(return_value=fake_pipe)

        await match_services_module.set_cache_with_index(
            cache_key_str="match:strict:plumbing:1",
            value="[]",
            ttl_seconds=60,
            mode="strict",
            skill="plumbing",
            b_lat=1,
            b_lon=2,
        )

        fake_pipe.set.assert_called_once_with("match:strict:plumbing:1", "[]", ex=60)
        fake_pipe.sadd.assert_called_once_with("matchkeys:strict:plumbing:lat=1:lon=2", "match:strict:plumbing:1")
        fake_pipe.expire.assert_called_once_with("matchkeys:strict:plumbing:lat=1:lon=2", 90)

    @pytest.mark.asyncio
    async def test_handyman_projection_count_returns_zero_on_error(self, match_services_module):
        match_services_module.redis_client.scard = AsyncMock(side_effect=RuntimeError("redis down"))

        result = await match_services_module.handyman_projection_count()

        assert result == 0

    @pytest.mark.asyncio
    async def test_availability_projection_count_returns_zero_on_error(self, match_services_module):
        match_services_module.redis_client.scard = AsyncMock(side_effect=RuntimeError("redis down"))

        result = await match_services_module.availability_projection_count()

        assert result == 0

    @pytest.mark.asyncio
    async def test_projections_have_any_availability_uses_count(self, match_services_module):
        match_services_module.availability_projection_count = AsyncMock(return_value=1)

        result = await match_services_module.projections_have_any_availability()

        assert result is True

    @pytest.mark.asyncio
    async def test_fetch_handymen_http_filters_invalid_rows(self, match_services_module, monkeypatch):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = [
            {"email": "a@example.com", "skills": ["plumbing"]},
            {"skills": ["missing-email"]},
            "bad-row",
        ]
        client = MagicMock()
        client.get = AsyncMock(return_value=response)

        class ClientCtx:
            async def __aenter__(self):
                return client

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(match_services_module.httpx, "AsyncClient", lambda timeout: ClientCtx())

        result = await match_services_module.fetch_handymen_http()

        assert len(result) == 1
        assert result[0]["email"] == "a@example.com"

    @pytest.mark.asyncio
    async def test_fetch_availability_http_returns_none_for_empty_email(self, match_services_module):
        result = await match_services_module.fetch_availability_http("")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_availability_http_returns_none_on_client_error(self, match_services_module, monkeypatch):
        class ClientCtx:
            async def __aenter__(self):
                raise RuntimeError("http failed")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(match_services_module.httpx, "AsyncClient", lambda timeout: ClientCtx())

        result = await match_services_module.fetch_availability_http("pro@example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_availability_http_filters_invalid_slots(self, match_services_module, monkeypatch):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "slots": [
                {"start": "2026-03-17T10:00:00+00:00", "end": "2026-03-17T12:00:00+00:00"},
                {"start": "2026-03-17T12:00:00+00:00", "end": "2026-03-17T11:00:00+00:00"},
                {"start": "bad", "end": "2026-03-17T13:00:00+00:00"},
            ]
        }
        client = MagicMock()
        client.get = AsyncMock(return_value=response)

        class ClientCtx:
            async def __aenter__(self):
                return client

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(match_services_module.httpx, "AsyncClient", lambda timeout: ClientCtx())

        result = await match_services_module.fetch_availability_http("pro@example.com")

        assert result == [{"start": "2026-03-17T10:00:00+00:00", "end": "2026-03-17T12:00:00+00:00"}]

    @pytest.mark.asyncio
    async def test_get_effective_availability_slots_returns_missing_when_live_absent(self, match_services_module):
        match_services_module.get_availability_slots = AsyncMock(return_value=None)
        match_services_module.fetch_availability_http = AsyncMock(return_value=None)

        slots, source = await match_services_module.get_effective_availability_slots("pro@example.com")

        assert slots is None
        assert source == "missing"

    @pytest.mark.asyncio
    async def test_seed_handyman_projection_if_empty_returns_existing_count(self, match_services_module):
        match_services_module.handyman_projection_count = AsyncMock(return_value=4)

        result = await match_services_module.seed_handyman_projection_if_empty()

        assert result == {"seeded": False, "reason": "already_present", "count": 4}

    @pytest.mark.asyncio
    async def test_seed_handyman_projection_if_empty_reports_fetch_failure(self, match_services_module):
        match_services_module.handyman_projection_count = AsyncMock(return_value=0)
        match_services_module.fetch_handymen_http = AsyncMock(side_effect=RuntimeError("upstream down"))

        result = await match_services_module.seed_handyman_projection_if_empty()

        assert result["seeded"] is False
        assert result["reason"].startswith("fetch_failed: RuntimeError")

    @pytest.mark.asyncio
    async def test_get_live_handymen_for_skill_returns_empty_for_blank_skill(self, match_services_module):
        result = await match_services_module.get_live_handymen_for_skill("  ")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_effective_handymen_for_skill_returns_empty_skill(self, match_services_module):
        handymen, source = await match_services_module.get_effective_handymen_for_skill("  ")

        assert handymen == []
        assert source == "empty-skill"

    @pytest.mark.asyncio
    async def test_get_effective_handymen_for_skill_falls_back_to_live(self, match_services_module):
        match_services_module.list_projected_handymen_by_skill = AsyncMock(return_value=[])
        match_services_module.get_live_handymen_for_skill = AsyncMock(return_value=[{"email": "a@example.com"}])

        handymen, source = await match_services_module.get_effective_handymen_for_skill("plumbing")

        assert handymen == [{"email": "a@example.com"}]
        assert source == "live"

    @pytest.mark.asyncio
    async def test_get_cached_result_reads_redis(self, match_services_module):
        match_services_module.redis_client.get = AsyncMock(return_value="cached")

        result = await match_services_module.get_cached_result("cache-key")

        assert result == "cached"