from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as redis_async

from shared.core.utils.datetime import as_utc, parse_dt
from shared.core.utils.normalize import clamp01, safe_float, safe_int
from tests.service_loader import load_service_app_module, REPO_ROOT

def _make_fake_redis():
    fake = MagicMock()
    fake.smembers = AsyncMock(return_value=set())
    fake.delete = AsyncMock(return_value=0)
    fake.get = AsyncMock(return_value=None)
    fake.set = AsyncMock(return_value=True)
    fake.scard = AsyncMock(return_value=0)
    fake.pipeline = MagicMock()
    return fake

def _bootstrap_match_package(package_name: str, monkeypatch):
    fake_redis = _make_fake_redis()

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("MATCH_DB", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(redis_async, "from_url", lambda *args, **kwargs: fake_redis)

    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)

    app_dir = REPO_ROOT / "services" / "match-service" / "app"
    app_dir_str = str(app_dir)
    if app_dir_str not in sys.path:
        sys.path.insert(0, app_dir_str)

    pkg = types.ModuleType(package_name)
    pkg.__path__ = [app_dir_str]
    sys.modules[package_name] = pkg

    app_pkg = types.ModuleType(f"{package_name}.application")
    app_pkg.__path__ = [str(app_dir / "application")]
    sys.modules[f"{package_name}.application"] = app_pkg

    mappers_path = app_dir / "application" / "mappers.py"
    mappers_mod = types.ModuleType(f"{package_name}.application.mappers")
    mappers_mod.__file__ = str(mappers_path)
    mappers_mod.__package__ = f"{package_name}.application"
    mappers_mod.as_utc = as_utc
    mappers_mod.parse_dt = parse_dt
    mappers_mod.clamp01 = clamp01
    mappers_mod.safe_float = safe_float
    mappers_mod.safe_int = safe_int
    sys.modules[f"{package_name}.application.mappers"] = mappers_mod

    return fake_redis

@pytest.fixture
def match_services_module(monkeypatch):
    fake_redis = _bootstrap_match_package("match_service_test_app", monkeypatch)

    module = load_service_app_module(
        "match-service",
        "application/services",
        package_name="match_service_test_app",
    )

    from match_service_test_app.application.normalizers import normalize_handyman, norm
    from match_service_test_app.domain.geo import (
        haversine, bucket_id, time_bucket, km_to_deg_lon, buckets_in_radius,
    )
    from match_service_test_app.infrastructure.cache_keys import cache_key
    from match_service_test_app.infrastructure.availability_projection import (
        projected_has_overlap, clean_slots, get_availability_slots,
        delete_availability_projection, availability_projection_count,
    )
    from match_service_test_app.infrastructure.projections import (
        get_handyman_projection, invalidate_bucket, get_cached_result,
        set_cache_with_index, handyman_projection_count,
        list_projected_handymen_by_skill, redis_client,
    )
    from match_service_test_app.infrastructure.clients import (
        fetch_handymen_http, fetch_availability_http,
        fetch_completed_jobs_counts_batch,
    )
    from match_service_test_app.domain.scoring import rank_match_candidates, compute_match_score
    from match_service_test_app.infrastructure.config import TIME_BUCKET_SECONDS

    attrs = {
        "normalize_handyman": normalize_handyman,
        "norm": norm,
        "parse_dt": parse_dt,
        "as_utc": as_utc,
        "haversine": haversine,
        "bucket_id": bucket_id,
        "time_bucket": time_bucket,
        "km_to_deg_lon": km_to_deg_lon,
        "buckets_in_radius": buckets_in_radius,
        "cache_key": cache_key,
        "projected_has_overlap": projected_has_overlap,
        "clean_slots": clean_slots,
        "get_handyman_projection": get_handyman_projection,
        "invalidate_bucket": invalidate_bucket,
        "get_cached_result": get_cached_result,
        "set_cache_with_index": set_cache_with_index,
        "rank_match_candidates": rank_match_candidates,
        "redis_client": fake_redis,
        "handyman_projection_count": handyman_projection_count,
        "list_projected_handymen_by_skill": list_projected_handymen_by_skill,
        "get_availability_slots": get_availability_slots,
        "delete_availability_projection": delete_availability_projection,
        "availability_projection_count": availability_projection_count,
        "fetch_handymen_http": fetch_handymen_http,
        "fetch_availability_http": fetch_availability_http,
        "fetch_completed_jobs_counts_batch": fetch_completed_jobs_counts_batch,
        "TIME_BUCKET_SECONDS": TIME_BUCKET_SECONDS,
        "compute_match_score": compute_match_score,
    }
    for name, value in attrs.items():
        setattr(module, name, value)

    return module

@pytest.fixture
def match_orchestrator_module(monkeypatch):
    _bootstrap_match_package("match_orchestrator_test_app", monkeypatch)

    module = load_service_app_module(
        "match-service",
        "application/match_orchestrator",
        package_name="match_orchestrator_test_app",
    )
    return module