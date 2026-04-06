from datetime import datetime, timedelta, timezone

import pytest

from shared.core.utils.intervals import overlaps, fully_contains

BASE_DT = datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)

@pytest.mark.unit
@pytest.mark.intervals
class TestOverlaps:
    @pytest.mark.parametrize("a, b, expected", [   
        ((0, 2), (1, 3), True), # partial overlap 
        ((1, 3), (0, 2), True), # commutative  
        ((0, 2), (4, 5), False), # no overlap (gap)
        ((0, 2), (2, 4), False), # adjacent (touching) → not overlapping
        ((0, 4), (1, 3), True), # complete containment
        ((0, 2), (0, 2), True), # identical
    ], ids=[
        "partial", "commutative", "gap", "adjacent",
        "contained", "identical",
    ])
    def test_overlap_cases(self, a, b, expected):
        a_start = BASE_DT + timedelta(hours=a[0])
        a_end = BASE_DT + timedelta(hours=a[1])
        b_start = BASE_DT + timedelta(hours=b[0])
        b_end = BASE_DT + timedelta(hours=b[1])

        assert overlaps(a_start, a_end, b_start, b_end) is expected

    def test_timezone_aware(self):
        a_start = BASE_DT
        a_end = BASE_DT + timedelta(hours=2)
        b_start = BASE_DT + timedelta(hours=1)
        b_end = BASE_DT + timedelta(hours=3)

        assert overlaps(a_start, a_end, b_start, b_end) is True

@pytest.mark.unit
@pytest.mark.intervals
class TestFullyContains:
    @pytest.mark.parametrize("outer, inner, expected", [
        # fully contained
        ((0, 4), (1, 3), True),
        # identical boundaries
        ((0, 2), (0, 2), True),
        # same start, shorter inner
        ((0, 4), (0, 2), True),
        # same end, later start
        ((0, 4), (2, 4), True),
        # partial overlap only
        ((0, 2), (1, 3), False),
        # inner extends before outer
        ((1, 4), (0, 3), False),
        # inner extends after outer
        ((0, 2), (0, 3), False),
        # zero-length inner at start
        ((0, 2), (0, 0), True),
        # no overlap at all
        ((0, 2), (4, 5), False),
    ], ids=[
        "contained", "identical", "same-start", "same-end",
        "partial", "before", "after", "zero-inner", "disjoint",
    ])
    def test_containment_cases(self, outer, inner, expected):
        outer_start = BASE_DT + timedelta(hours=outer[0])
        outer_end = BASE_DT + timedelta(hours=outer[1])
        inner_start = BASE_DT + timedelta(hours=inner[0])
        inner_end = BASE_DT + timedelta(hours=inner[1])

        assert fully_contains(outer_start, outer_end, inner_start, inner_end) is expected