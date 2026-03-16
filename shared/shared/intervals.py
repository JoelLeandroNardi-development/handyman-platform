from __future__ import annotations

from datetime import datetime


def overlaps(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> bool:
    return a_start < b_end and a_end > b_start


def fully_contains(
    outer_start: datetime,
    outer_end: datetime,
    inner_start: datetime,
    inner_end: datetime,
) -> bool:
    return outer_start <= inner_start and outer_end >= inner_end
