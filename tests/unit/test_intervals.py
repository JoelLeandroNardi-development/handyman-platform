from datetime import datetime, timedelta, timezone

import pytest

from shared.shared.intervals import overlaps, fully_contains


@pytest.mark.unit
@pytest.mark.intervals
class TestOverlaps:
    
    def test_overlaps_partial_overlap(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        b_start, b_end = sample_intervals["interval_b"]
        
        assert overlaps(a_start, a_end, b_start, b_end) is True
        assert overlaps(b_start, b_end, a_start, a_end) is True
    
    def test_no_overlap_adjacent_intervals(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        c_start, c_end = sample_intervals["interval_c"]
        
        assert overlaps(a_start, a_end, c_start, c_end) is False
        assert overlaps(c_start, c_end, a_start, a_end) is False
    
    def test_no_overlap_one_ends_when_other_starts(self, sample_intervals):
        a_start = sample_intervals["interval_a"][0]
        a_end = sample_intervals["interval_a"][1]
        
        b_start = a_end
        b_end = b_start + timedelta(hours=2)
        
        assert overlaps(a_start, a_end, b_start, b_end) is False
    
    def test_complete_overlap_one_contains_other(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        
        inner_start = a_start + timedelta(minutes=30)
        inner_end = a_end - timedelta(minutes=30)
        
        assert overlaps(a_start, a_end, inner_start, inner_end) is True
        assert overlaps(inner_start, inner_end, a_start, a_end) is True
    
    def test_identical_intervals(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        
        assert overlaps(a_start, a_end, a_start, a_end) is True
    
    def test_single_point_no_overlap(self, sample_intervals):
        a_start = sample_intervals["interval_a"][0]
        a_end = sample_intervals["interval_a"][1]
        
        b_start = a_end
        b_end = b_start + timedelta(hours=1)
        
        assert overlaps(a_start, a_end, b_start, b_end) is False
    
    def test_overlaps_with_timezone_aware_datetimes(self):
        utc = timezone.utc
        base_utc = datetime(2026, 3, 17, 10, 0, 0, tzinfo=utc)
        
        a_start = base_utc
        a_end = base_utc + timedelta(hours=2)
        
        b_start = base_utc + timedelta(hours=1)
        b_end = base_utc + timedelta(hours=3)
        
        assert overlaps(a_start, a_end, b_start, b_end) is True


@pytest.mark.unit
@pytest.mark.intervals
class TestFullyContains:
    
    def test_fully_contains_complete_container(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        d_start, d_end = sample_intervals["interval_d"]
        
        assert fully_contains(a_start, a_end, d_start, d_end) is True
    
    def test_not_fully_contains_partial_overlap(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        b_start, b_end = sample_intervals["interval_b"]
        
        assert fully_contains(a_start, a_end, b_start, b_end) is False
        assert fully_contains(b_start, b_end, a_start, a_end) is False
    
    def test_fully_contains_identical_intervals(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        
        assert fully_contains(a_start, a_end, a_start, a_end) is True
    
    def test_not_fully_contains_no_overlap(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        c_start, c_end = sample_intervals["interval_c"]
        
        assert fully_contains(a_start, a_end, c_start, c_end) is False
        assert fully_contains(c_start, c_end, a_start, a_end) is False
    
    def test_fully_contains_same_start_different_end(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        
        inner_start = a_start
        inner_end = a_end - timedelta(minutes=30)
        
        assert fully_contains(a_start, a_end, inner_start, inner_end) is True
        assert fully_contains(inner_start, inner_end, a_start, a_end) is False
    
    def test_fully_contains_same_end_different_start(self, sample_intervals):
        a_start, a_end = sample_intervals["interval_a"]
        
        inner_start = a_start + timedelta(minutes=30)
        inner_end = a_end
        
        assert fully_contains(a_start, a_end, inner_start, inner_end) is True
        assert fully_contains(inner_start, inner_end, a_start, a_end) is False
    
    def test_fully_contains_inner_point_intervals(self):
        base = datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)
        
        outer_start = base
        outer_end = base + timedelta(hours=2)
        
        point_time = base
        point_end = base
        
        assert fully_contains(outer_start, outer_end, point_time, point_end) is True
    
    def test_fully_contains_boundary_cases(self):
        base = datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)
        
        outer_start = base
        outer_end = base + timedelta(hours=2)
        
        assert fully_contains(outer_start, outer_end, outer_start, outer_end) is True
        
        too_early_start = outer_start - timedelta(minutes=1)
        assert fully_contains(outer_start, outer_end, too_early_start, outer_end) is False
        
        too_late_end = outer_end + timedelta(minutes=1)
        assert fully_contains(outer_start, outer_end, outer_start, too_late_end) is False
