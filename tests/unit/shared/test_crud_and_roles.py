from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from shared.core.db.crud import apply_partial_update, fetch_or_404
from shared.core.auth.roles import normalize_roles

Base = declarative_base()

class _DummyModel(Base):
    __tablename__ = "dummy_model"
    id = Column(Integer, primary_key=True)
    name = Column(String)

@pytest.mark.unit
class TestFetchOr404:
    @pytest.mark.asyncio
    async def test_returns_entity(self):
        entity = object()
        proxy = MagicMock(scalar_one_or_none=MagicMock(return_value=entity))
        db = MagicMock(execute=AsyncMock(return_value=proxy))

        assert await fetch_or_404(db, _DummyModel, filter_column=_DummyModel.id, filter_value="abc") is entity

    @pytest.mark.asyncio
    async def test_raises_404(self):
        proxy = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db = MagicMock(execute=AsyncMock(return_value=proxy))

        with pytest.raises(HTTPException) as exc:
            await fetch_or_404(db, _DummyModel, filter_column=_DummyModel.id, filter_value="abc", detail="Not found")
        assert exc.value.status_code == 404

@pytest.mark.unit
class TestApplyPartialUpdate:
    def test_sets_only_non_none(self):
        entity = SimpleNamespace(name="old", status="pending", count=1)
        data = SimpleNamespace(name="new", status=None, count=3)

        apply_partial_update(entity, data, ["name", "status", "count"])

        assert entity.name == "new"
        assert entity.status == "pending"
        assert entity.count == 3

@pytest.mark.unit
class TestNormalizeRoles:
    def test_deduplicates_and_normalizes(self):
        assert normalize_roles([" Admin ", "user", "admin"]) == ["admin", "user"]

    def test_raises_on_invalid_role(self):
        with pytest.raises(ValueError):
            normalize_roles(["superuser"])

    def test_uses_default_when_empty(self):
        assert normalize_roles([], default=["user"]) == ["user"]

    def test_allows_empty_when_requested(self):
        assert normalize_roles([], allow_empty=True) == []

    def test_rejects_empty_without_default(self):
        with pytest.raises(ValueError):
            normalize_roles([])