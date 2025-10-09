"""Tests for UTC time discipline (Phase 0, Point 3)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from kira.core.time import (
    DayWindow,
    WeekWindow,
    format_utc_iso8601,
    get_current_utc,
    get_day_window_utc,
    get_week_window_utc,
    is_dst_transition_day,
    localize_utc_to_tz,
    parse_utc_iso8601,
)


def test_get_current_utc():
    """Test getting current UTC time."""
    now = get_current_utc()

    assert now.tzinfo == UTC
    assert isinstance(now, datetime)


def test_format_utc_iso8601_with_utc():
    """Test formatting UTC datetime to ISO-8601."""
    dt = datetime(2025, 10, 8, 12, 30, 0, tzinfo=UTC)
    result = format_utc_iso8601(dt)

    assert result == "2025-10-08T12:30:00+00:00"


def test_format_utc_iso8601_with_local_tz():
    """Test formatting local timezone datetime to ISO-8601 UTC."""
    # Brussels time (UTC+2 in summer)
    tz = ZoneInfo("Europe/Brussels")
    dt = datetime(2025, 10, 8, 14, 30, 0, tzinfo=tz)
    result = format_utc_iso8601(dt)

    # Should convert to UTC (14:30 Brussels = 12:30 UTC)
    assert result == "2025-10-08T12:30:00+00:00"


def test_format_utc_iso8601_naive_datetime():
    """Test formatting naive datetime (assumes UTC)."""
    dt = datetime(2025, 10, 8, 12, 30, 0)
    result = format_utc_iso8601(dt)

    assert result == "2025-10-08T12:30:00+00:00"


def test_parse_utc_iso8601_with_utc():
    """Test parsing ISO-8601 UTC string."""
    result = parse_utc_iso8601("2025-10-08T12:30:00+00:00")

    assert result.year == 2025
    assert result.month == 10
    assert result.day == 8
    assert result.hour == 12
    assert result.minute == 30
    assert result.tzinfo == UTC


def test_parse_utc_iso8601_with_z_suffix():
    """Test parsing ISO-8601 with Z suffix (Zulu time)."""
    result = parse_utc_iso8601("2025-10-08T12:30:00Z")

    assert result.hour == 12
    assert result.tzinfo == UTC


def test_parse_utc_iso8601_with_offset():
    """Test parsing ISO-8601 with timezone offset."""
    result = parse_utc_iso8601("2025-10-08T14:30:00+02:00")

    # Should convert to UTC (14:30+02:00 = 12:30 UTC)
    assert result.hour == 12
    assert result.tzinfo == UTC


def test_localize_utc_to_tz():
    """Test localizing UTC to specific timezone."""
    utc_dt = datetime(2025, 10, 8, 12, 0, 0, tzinfo=UTC)

    # Localize to Brussels (UTC+2 in summer)
    local_dt = localize_utc_to_tz(utc_dt, "Europe/Brussels")

    assert local_dt.hour == 14
    assert local_dt.tzinfo == ZoneInfo("Europe/Brussels")


def test_localize_utc_to_tz_with_zoneinfo():
    """Test localization with ZoneInfo object."""
    utc_dt = datetime(2025, 10, 8, 12, 0, 0, tzinfo=UTC)
    tz = ZoneInfo("America/New_York")

    local_dt = localize_utc_to_tz(utc_dt, tz)

    # New York is UTC-4 in summer
    assert local_dt.hour == 8
    assert local_dt.tzinfo == tz


def test_get_day_window_utc_regular_day():
    """Test getting day window for a regular day (no DST)."""
    # October 8, 2025 in Brussels (no DST transition)
    window = get_day_window_utc("2025-10-08", "Europe/Brussels")

    assert isinstance(window, DayWindow)
    assert window.local_date == "2025-10-08"
    assert window.timezone_name == "Europe/Brussels"

    # Brussels is UTC+2 in summer
    # Midnight Brussels = 22:00 previous day UTC
    assert window.start_utc.day == 7
    assert window.start_utc.hour == 22

    assert window.end_utc.day == 8
    assert window.end_utc.hour == 22

    # 24 hours apart
    duration = window.end_utc - window.start_utc
    assert duration.total_seconds() == 24 * 3600


def test_get_day_window_utc_dst_spring_forward():
    """Test day window for DST spring forward day (23 hours).

    Phase 0, Point 3 DoD: Unit tests cover DST transitions.
    """
    # March 30, 2025: DST starts in Europe (clocks skip from 02:00 to 03:00)
    window = get_day_window_utc("2025-03-30", "Europe/Brussels")

    assert window.local_date == "2025-03-30"
    assert window.has_dst_transition is True

    # This day is only 23 hours long (loses 1 hour)
    duration = window.end_utc - window.start_utc
    assert duration.total_seconds() == 23 * 3600


def test_get_day_window_utc_dst_fall_back():
    """Test day window for DST fall back day (25 hours).

    Phase 0, Point 3 DoD: Unit tests cover DST transitions.
    """
    # October 26, 2025: DST ends in Europe (clocks go from 03:00 back to 02:00)
    window = get_day_window_utc("2025-10-26", "Europe/Brussels")

    assert window.local_date == "2025-10-26"
    assert window.has_dst_transition is True

    # This day is 25 hours long (gains 1 hour)
    duration = window.end_utc - window.start_utc
    assert duration.total_seconds() == 25 * 3600


def test_get_week_window_utc_regular_week():
    """Test getting week window for a regular week."""
    # Week starting Monday, October 6, 2025
    window = get_week_window_utc("2025-10-06", "Europe/Brussels")

    assert isinstance(window, WeekWindow)
    assert window.week_start_date == "2025-10-06"
    assert window.timezone_name == "Europe/Brussels"

    # Should be 7 days = 168 hours
    duration = window.end_utc - window.start_utc
    assert duration.total_seconds() == 7 * 24 * 3600


def test_get_week_window_utc_with_dst_transition():
    """Test week window containing DST transition.

    Phase 0, Point 3 DoD: Unit tests cover DST transitions.
    """
    # Week containing October 26, 2025 (DST ends)
    # Monday October 20 - Sunday October 26
    window = get_week_window_utc("2025-10-20", "Europe/Brussels")

    assert window.week_start_date == "2025-10-20"
    assert window.has_dst_transition is True

    # This week is 169 hours long (25-hour Sunday)
    duration = window.end_utc - window.start_utc
    assert duration.total_seconds() == 169 * 3600


def test_get_week_window_utc_not_monday_raises_error():
    """Test that week window requires Monday."""
    # October 8, 2025 is a Wednesday
    with pytest.raises(ValueError, match="not a Monday"):
        get_week_window_utc("2025-10-08", "Europe/Brussels")


def test_is_dst_transition_day_spring_forward():
    """Test DST detection for spring forward day.

    Phase 0, Point 3 DoD: Unit tests cover DST transitions.
    """
    tz = ZoneInfo("Europe/Brussels")

    # March 30, 2025: DST starts
    transition_date = date(2025, 3, 30)
    assert is_dst_transition_day(transition_date, tz) is True

    # Day before: no transition
    assert is_dst_transition_day(date(2025, 3, 29), tz) is False

    # Day after: no transition
    assert is_dst_transition_day(date(2025, 3, 31), tz) is False


def test_is_dst_transition_day_fall_back():
    """Test DST detection for fall back day.

    Phase 0, Point 3 DoD: Unit tests cover DST transitions.
    """
    tz = ZoneInfo("Europe/Brussels")

    # October 26, 2025: DST ends
    transition_date = date(2025, 10, 26)
    assert is_dst_transition_day(transition_date, tz) is True

    # Day before: no transition
    assert is_dst_transition_day(date(2025, 10, 25), tz) is False

    # Day after: no transition
    assert is_dst_transition_day(date(2025, 10, 27), tz) is False


def test_is_dst_transition_day_with_datetime():
    """Test DST detection accepts datetime objects."""
    tz = ZoneInfo("Europe/Brussels")

    # March 30, 2025 as datetime
    transition_dt = datetime(2025, 3, 30, 12, 0, 0)
    assert is_dst_transition_day(transition_dt, tz) is True


def test_is_dst_transition_day_different_tz():
    """Test DST transitions in different timezones."""
    # US Eastern time has different DST dates
    us_tz = ZoneInfo("America/New_York")

    # March 9, 2025: DST starts in US
    assert is_dst_transition_day(date(2025, 3, 9), us_tz) is True

    # November 2, 2025: DST ends in US
    assert is_dst_transition_day(date(2025, 11, 2), us_tz) is True

    # October 26 has no DST transition in US
    assert is_dst_transition_day(date(2025, 10, 26), us_tz) is False


def test_round_trip_utc_formatting():
    """Test format→parse→format yields identical result."""
    original_dt = datetime(2025, 10, 8, 12, 30, 45, tzinfo=UTC)

    # Format
    iso_str = format_utc_iso8601(original_dt)

    # Parse
    parsed_dt = parse_utc_iso8601(iso_str)

    # Format again
    iso_str2 = format_utc_iso8601(parsed_dt)

    assert iso_str == iso_str2
    assert parsed_dt == original_dt


def test_utc_discipline_no_local_times_in_storage():
    """Test that all persistence uses UTC (Phase 0, Point 3 DoD)."""
    # Create a local time
    local_dt = datetime(2025, 10, 8, 14, 30, 0, tzinfo=ZoneInfo("Europe/Brussels"))

    # Format for storage - should convert to UTC
    stored = format_utc_iso8601(local_dt)

    # Verify stored value is UTC
    assert "+00:00" in stored

    # Parse back
    retrieved = parse_utc_iso8601(stored)
    assert retrieved.tzinfo == UTC

    # UTC hour should be 12:30 (14:30 Brussels - 2 hours)
    assert retrieved.hour == 12


def test_localization_for_display_only():
    """Test that localization is for display, not storage."""
    # Storage: always UTC
    utc_dt = datetime(2025, 10, 8, 12, 0, 0, tzinfo=UTC)
    stored = format_utc_iso8601(utc_dt)
    assert "+00:00" in stored

    # Display: can be localized
    display_brussels = localize_utc_to_tz(utc_dt, "Europe/Brussels")
    assert display_brussels.hour == 14

    display_ny = localize_utc_to_tz(utc_dt, "America/New_York")
    assert display_ny.hour == 8

    # But storage always uses UTC
    stored_brussels = format_utc_iso8601(display_brussels)
    stored_ny = format_utc_iso8601(display_ny)

    assert stored_brussels == stored
    assert stored_ny == stored
