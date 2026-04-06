from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from shared.core.utils.datetime import as_utc, parse_dt, utc_now_iso

@pytest.mark.unit
class TestUtcNowIso:
    def test_returns_iso_string(self):
        result = utc_now_iso()
        assert isinstance(result, str)
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None

    def test_is_close_to_now(self):
        now = datetime.now(timezone.utc)
        result = datetime.fromisoformat(utc_now_iso())
        assert abs((result - now).total_seconds()) < 2

@pytest.mark.unit
class TestAsUtc:
    def test_naive_gets_utc_attached(self):
        naive = datetime(2025, 1, 15, 12, 0, 0)
        result = as_utc(naive)
        assert result.tzinfo == timezone.utc
        assert result.hour == 12

    def test_utc_stays_utc(self):
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = as_utc(dt)
        assert result.tzinfo == timezone.utc
        assert result == dt

    def test_non_utc_converted(self):
        eastern = timezone(timedelta(hours=-5))
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=eastern)
        result = as_utc(dt)
        assert result.tzinfo == timezone.utc
        assert result.hour == 17

@pytest.mark.unit
class TestParseDt:
    def test_parses_iso_string(self):
        result = parse_dt("2025-06-15T10:30:00+00:00")
        assert result.tzinfo == timezone.utc
        assert result.hour == 10

    def test_passes_through_datetime(self):
        dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = parse_dt(dt)
        assert result is not dt or result == dt
        assert result.tzinfo == timezone.utc

    def test_naive_isoformat_gets_utc(self):
        result = parse_dt("2025-06-15T10:30:00")
        assert result.tzinfo == timezone.utc

    @pytest.mark.parametrize("bad_input", [123, None, [], {}])
    def test_unsupported_type_raises(self, bad_input):
        with pytest.raises(ValueError, match="Unsupported datetime type"):
            parse_dt(bad_input)