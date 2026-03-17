from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from shared.shared.crud_helpers import apply_partial_update, fetch_or_404
from shared.shared.roles import normalize_roles


Base = declarative_base()


class DummyModel(Base):
    __tablename__ = "dummy_model"

    id = Column(Integer, primary_key=True)
    name = Column(String)


@pytest.mark.unit
class TestCrudHelpers:

    @pytest.mark.asyncio
    async def test_fetch_or_404_returns_entity(self):
        entity = object()
        result_proxy = MagicMock()
        result_proxy.scalar_one_or_none.return_value = entity
        db = MagicMock()
        db.execute = AsyncMock(return_value=result_proxy)

        result = await fetch_or_404(
            db,
            DummyModel,
            filter_column=DummyModel.id,
            filter_value="abc",
        )

        assert result is entity

    @pytest.mark.asyncio
    async def test_fetch_or_404_raises_http_404(self):
        result_proxy = MagicMock()
        result_proxy.scalar_one_or_none.return_value = None
        db = MagicMock()
        db.execute = AsyncMock(return_value=result_proxy)

        with pytest.raises(HTTPException) as exc_info:
            await fetch_or_404(
                db,
                DummyModel,
                filter_column=DummyModel.id,
                filter_value="abc",
                detail="Booking not found",
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Booking not found"

    def test_apply_partial_update_sets_only_non_none_values(self):
        entity = SimpleNamespace(name="old", status="pending", count=1)
        data = SimpleNamespace(name="new", status=None, count=3)

        apply_partial_update(entity, data, ["name", "status", "count"])

        assert entity.name == "new"
        assert entity.status == "pending"
        assert entity.count == 3


@pytest.mark.unit
class TestRoles:

    def test_normalize_roles_deduplicates_and_normalizes(self):
        result = normalize_roles([" Admin ", "user", "admin"])

        assert result == ["admin", "user"]

    def test_normalize_roles_raises_on_invalid_role(self):
        with pytest.raises(ValueError):
            normalize_roles(["superuser"])

    def test_normalize_roles_uses_default_when_empty(self):
        result = normalize_roles([], default=["user"])

        assert result == ["user"]

    def test_normalize_roles_allows_empty_when_requested(self):
        result = normalize_roles([], allow_empty=True)

        assert result == []

    def test_normalize_roles_rejects_empty_without_default(self):
        with pytest.raises(ValueError):
            normalize_roles([])