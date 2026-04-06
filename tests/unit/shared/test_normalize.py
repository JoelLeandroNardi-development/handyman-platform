from __future__ import annotations

import pytest

from shared.core.utils.normalize import clamp01, norm, safe_float, safe_int

@pytest.mark.unit
class TestNorm:
    @pytest.mark.parametrize("raw, expected", [
        ("Hello", "hello"),
        ("  TRIM  ", "trim"),
        ("", ""),
        (None, ""),
    ])
    def test_normalises_and_strips(self, raw, expected):
        assert norm(raw) == expected

@pytest.mark.unit
class TestSafeFloat:
    @pytest.mark.parametrize("value, expected", [
        (3.14, 3.14),
        ("2.5", 2.5),
        (0, 0.0),
        ("0", 0.0),
        (True, 1.0),
    ])
    def test_valid_conversions(self, value, expected):
        assert safe_float(value) == expected

    @pytest.mark.parametrize("value", ["abc", None, object(), []])
    def test_invalid_returns_default(self, value):
        assert safe_float(value) == 0.0

    def test_custom_default(self):
        assert safe_float("bad", default=-1.0) == -1.0

@pytest.mark.unit
class TestSafeInt:
    @pytest.mark.parametrize("value, expected", [
        (42, 42),
        ("7", 7),
        (3.9, 3),
        (True, 1),
    ])
    def test_valid_conversions(self, value, expected):
        assert safe_int(value) == expected

    @pytest.mark.parametrize("value", ["xyz", None, object(), []])
    def test_invalid_returns_default(self, value):
        assert safe_int(value) == 0

    def test_custom_default(self):
        assert safe_int("bad", default=-1) == -1

@pytest.mark.unit
class TestClamp01:
    @pytest.mark.parametrize("value, expected", [
        (0.5, 0.5),
        (0.0, 0.0),
        (1.0, 1.0),
        (-0.5, 0.0),
        (1.5, 1.0),
        (-100.0, 0.0),
        (100.0, 1.0),
    ])
    def test_clamps_value(self, value, expected):
        assert clamp01(value) == expected