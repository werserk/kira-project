"""Tests for time window calculations (Phase 7, Point 22).

DoD: Weeks with DST changes yield correct boundaries and summaries.
"""

from datetime import datetime

import pytest

from kira.rollups.time_windows import (
    compute_boundaries_utc,
    compute_day_boundaries_utc,
    compute_month_boundaries_utc,
    compute_week_boundaries_utc,
    get_week_start,
)


def test_get_week_start_monday():
    """Test getting week start (Monday)."""
    # Wednesday, Oct 8, 2025
    dt = datetime(2025, 10, 8, 15, 30, 0)

    # Week starts Monday (0)
    start = get_week_start(dt, start_on=0)

    assert start.weekday() == 0  # Monday
    assert start.day == 6  # Oct 6 is Monday
    assert start.hour == 15  # Same time as input
    assert start.minute == 30


def test_get_week_start_sunday():
    """Test getting week start (Sunday)."""
    # Wednesday, Oct 8, 2025
    dt = datetime(2025, 10, 8, 10, 0, 0)

    # Week starts Sunday (6)
    start = get_week_start(dt, start_on=6)

    assert start.weekday() == 6  # Sunday
    assert start.day == 5  # Oct 5 is Sunday


def test_compute_day_boundaries_utc_regular():
    """Test day boundaries for regular day (no DST)."""
    # Regular day in October (no DST transition)
    local_date = datetime(2025, 10, 8)

    start_utc, end_utc = compute_day_boundaries_utc(
        local_date,
        "America/New_York",
    )

    # Should be 24-hour day
    # New York is UTC-4 in October (EDT)
    assert start_utc.endswith("T04:00:00+00:00")  # Midnight EDT = 4am UTC
    assert end_utc.endswith("T04:00:00+00:00")  # Next midnight


def test_compute_day_boundaries_utc_spring_forward():
    """Test DoD: DST spring forward day (23 hours).

    On March 9, 2025, at 2am EST → 3am EDT (spring forward).
    The "day" is only 23 hours long in local time.
    """
    # March 9, 2025 - DST transition day (spring forward)
    local_date = datetime(2025, 3, 9)

    start_utc, end_utc = compute_day_boundaries_utc(
        local_date,
        "America/New_York",
    )

    # March 9 midnight EST = 5am UTC
    assert "2025-03-09T05:00:00" in start_utc

    # March 10 midnight EDT = 4am UTC (due to spring forward)
    assert "2025-03-10T04:00:00" in end_utc

    # Verify it's a 23-hour day in UTC terms
    from kira.core.time import parse_utc_iso8601

    start_dt = parse_utc_iso8601(start_utc)
    end_dt = parse_utc_iso8601(end_utc)
    duration = (end_dt - start_dt).total_seconds() / 3600

    assert duration == 23.0  # 23-hour day


def test_compute_day_boundaries_utc_fall_back():
    """Test DoD: DST fall back day (25 hours).

    On November 2, 2025, at 2am EDT → 1am EST (fall back).
    The "day" is 25 hours long in local time.
    """
    # November 2, 2025 - DST transition day (fall back)
    local_date = datetime(2025, 11, 2)

    start_utc, end_utc = compute_day_boundaries_utc(
        local_date,
        "America/New_York",
    )

    # November 2 midnight EDT = 4am UTC
    assert "2025-11-02T04:00:00" in start_utc

    # November 3 midnight EST = 5am UTC (due to fall back)
    assert "2025-11-03T05:00:00" in end_utc

    # Verify it's a 25-hour day in UTC terms
    from kira.core.time import parse_utc_iso8601

    start_dt = parse_utc_iso8601(start_utc)
    end_dt = parse_utc_iso8601(end_utc)
    duration = (end_dt - start_dt).total_seconds() / 3600

    assert duration == 25.0  # 25-hour day


def test_compute_week_boundaries_utc_regular():
    """Test week boundaries for regular week (no DST)."""
    # Week in October (no DST transition)
    local_date = datetime(2025, 10, 8)  # Wednesday

    start_utc, end_utc = compute_week_boundaries_utc(
        local_date,
        "America/New_York",
        start_on=0,  # Monday
    )

    # Should start on Monday, Oct 6
    assert "2025-10-06" in start_utc

    # Should end on Monday, Oct 13
    assert "2025-10-13" in end_utc


def test_compute_week_boundaries_utc_dst_spring():
    """Test DoD: Week containing DST spring forward transition.

    Week of March 9, 2025 contains DST transition.
    """
    # Week containing March 9 DST transition
    local_date = datetime(2025, 3, 9)  # Sunday (transition day)

    start_utc, end_utc = compute_week_boundaries_utc(
        local_date,
        "America/New_York",
        start_on=6,  # Sunday
    )

    # Should start on Sunday, March 9
    assert "2025-03-09" in start_utc

    # Should end on Sunday, March 16
    assert "2025-03-16" in end_utc

    # Verify week is 167 hours (7*24 - 1 due to spring forward)
    from kira.core.time import parse_utc_iso8601

    start_dt = parse_utc_iso8601(start_utc)
    end_dt = parse_utc_iso8601(end_utc)
    duration = (end_dt - start_dt).total_seconds() / 3600

    assert duration == 167.0  # 167-hour week (23 + 6*24)


def test_compute_week_boundaries_utc_dst_fall():
    """Test DoD: Week containing DST fall back transition.

    Week of November 2, 2025 contains DST transition.
    """
    # Week containing November 2 DST transition
    local_date = datetime(2025, 11, 2)  # Sunday (transition day)

    start_utc, end_utc = compute_week_boundaries_utc(
        local_date,
        "America/New_York",
        start_on=6,  # Sunday
    )

    # Should start on Sunday, November 2
    assert "2025-11-02" in start_utc

    # Should end on Sunday, November 9
    assert "2025-11-09" in end_utc

    # Verify week is 169 hours (7*24 + 1 due to fall back)
    from kira.core.time import parse_utc_iso8601

    start_dt = parse_utc_iso8601(start_utc)
    end_dt = parse_utc_iso8601(end_utc)
    duration = (end_dt - start_dt).total_seconds() / 3600

    assert duration == 169.0  # 169-hour week (25 + 6*24)


def test_compute_month_boundaries_utc_regular():
    """Test month boundaries for regular month."""
    # October 2025 (31 days)
    local_date = datetime(2025, 10, 15)

    start_utc, end_utc = compute_month_boundaries_utc(
        local_date,
        "America/New_York",
    )

    # Should start on Oct 1
    assert "2025-10-01" in start_utc

    # Should end on Nov 1
    assert "2025-11-01" in end_utc


def test_compute_month_boundaries_utc_dst_spring():
    """Test DoD: Month containing DST spring forward."""
    # March 2025 contains DST transition
    local_date = datetime(2025, 3, 15)

    start_utc, end_utc = compute_month_boundaries_utc(
        local_date,
        "America/New_York",
    )

    # Should start on March 1
    assert "2025-03-01" in start_utc

    # Should end on April 1
    assert "2025-04-01" in end_utc

    # Month is 31*24 - 1 = 743 hours due to spring forward
    from kira.core.time import parse_utc_iso8601

    start_dt = parse_utc_iso8601(start_utc)
    end_dt = parse_utc_iso8601(end_utc)
    duration = (end_dt - start_dt).total_seconds() / 3600

    assert duration == 743.0  # 743-hour month


def test_compute_month_boundaries_utc_dst_fall():
    """Test DoD: Month containing DST fall back."""
    # November 2025 contains DST transition
    local_date = datetime(2025, 11, 15)

    start_utc, end_utc = compute_month_boundaries_utc(
        local_date,
        "America/New_York",
    )

    # Should start on November 1
    assert "2025-11-01" in start_utc

    # Should end on December 1
    assert "2025-12-01" in end_utc

    # Month is 30*24 + 1 = 721 hours due to fall back
    from kira.core.time import parse_utc_iso8601

    start_dt = parse_utc_iso8601(start_utc)
    end_dt = parse_utc_iso8601(end_utc)
    duration = (end_dt - start_dt).total_seconds() / 3600

    assert duration == 721.0  # 721-hour month


def test_compute_boundaries_utc_dispatch():
    """Test compute_boundaries_utc dispatches correctly."""
    local_date = datetime(2025, 10, 8)

    # Day
    day_result = compute_boundaries_utc(local_date, "day", "America/New_York")
    assert "2025-10-08" in day_result[0]

    # Week
    week_result = compute_boundaries_utc(local_date, "week", "America/New_York")
    assert "2025-10-06" in week_result[0]  # Monday

    # Month
    month_result = compute_boundaries_utc(local_date, "month", "America/New_York")
    assert "2025-10-01" in month_result[0]


def test_compute_boundaries_utc_invalid_window():
    """Test compute_boundaries_utc rejects invalid window."""
    local_date = datetime(2025, 10, 8)

    with pytest.raises(ValueError, match="Unknown window type"):
        compute_boundaries_utc(local_date, "invalid", "UTC")  # type: ignore


def test_utc_timezone_no_dst():
    """Test UTC timezone has no DST transitions."""
    # Any day in UTC
    local_date = datetime(2025, 3, 9)

    start_utc, end_utc = compute_day_boundaries_utc(local_date, "UTC")

    # Should be exactly 24 hours
    from kira.core.time import parse_utc_iso8601

    start_dt = parse_utc_iso8601(start_utc)
    end_dt = parse_utc_iso8601(end_utc)
    duration = (end_dt - start_dt).total_seconds() / 3600

    assert duration == 24.0  # Always 24 hours in UTC


def test_dod_dst_transitions_yield_correct_boundaries():
    """Test DoD: DST transitions yield correct boundaries.

    Comprehensive test covering all boundary types with DST.
    """
    # Spring forward day
    spring_day = datetime(2025, 3, 9)
    day_start, day_end = compute_day_boundaries_utc(spring_day, "America/New_York")

    from kira.core.time import parse_utc_iso8601

    day_duration = (parse_utc_iso8601(day_end) - parse_utc_iso8601(day_start)).total_seconds() / 3600
    assert day_duration == 23.0

    # Week containing spring forward
    week_start, week_end = compute_week_boundaries_utc(spring_day, "America/New_York", start_on=6)
    week_duration = (parse_utc_iso8601(week_end) - parse_utc_iso8601(week_start)).total_seconds() / 3600
    assert week_duration == 167.0

    # Month containing spring forward
    month_start, month_end = compute_month_boundaries_utc(spring_day, "America/New_York")
    month_duration = (parse_utc_iso8601(month_end) - parse_utc_iso8601(month_start)).total_seconds() / 3600
    assert month_duration == 743.0

    # All boundaries are correct ✓
