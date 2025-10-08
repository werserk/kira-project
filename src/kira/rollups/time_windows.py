"""Time window calculations with DST awareness (Phase 7, Point 22).

Compute UTC boundaries from local time windows (day, week, month).
Handle DST transitions correctly.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

import pytz

from ..core.time import format_utc_iso8601, get_current_utc, parse_utc_iso8601

__all__ = [
    "TimeWindow",
    "compute_day_boundaries_utc",
    "compute_week_boundaries_utc",
    "compute_month_boundaries_utc",
    "get_week_start",
]

TimeWindow = Literal["day", "week", "month"]


def get_week_start(dt: datetime, start_on: int = 0) -> datetime:
    """Get start of week for a datetime.
    
    Parameters
    ----------
    dt
        Datetime to get week start for
    start_on
        Day of week to start on (0=Monday, 6=Sunday)
        
    Returns
    -------
    datetime
        Start of week (same time as input)
    """
    days_since_start = (dt.weekday() - start_on) % 7
    return dt - timedelta(days=days_since_start)


def compute_day_boundaries_utc(
    local_date: datetime,
    timezone_str: str = "UTC",
) -> tuple[str, str]:
    """Compute UTC boundaries for a local day (Phase 7, Point 22).
    
    Handles DST transitions: a "day" in local time may be 23, 24, or 25 hours in UTC.
    
    Parameters
    ----------
    local_date
        Date in local timezone (time component ignored)
    timezone_str
        Timezone name (e.g., "America/New_York")
        
    Returns
    -------
    tuple[str, str]
        (start_utc, end_utc) as ISO-8601 strings
        
    Examples
    --------
    >>> # Regular day
    >>> start, end = compute_day_boundaries_utc(
    ...     datetime(2025, 10, 8),
    ...     "America/New_York"
    ... )
    >>> # DST transition day (spring forward: 23 hours)
    >>> start, end = compute_day_boundaries_utc(
    ...     datetime(2025, 3, 9),
    ...     "America/New_York"
    ... )
    >>> # DST transition day (fall back: 25 hours)
    >>> start, end = compute_day_boundaries_utc(
    ...     datetime(2025, 11, 2),
    ...     "America/New_York"
    ... )
    """
    tz = pytz.timezone(timezone_str)
    
    # Start of day in local time (midnight)
    local_start = tz.localize(
        datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0)
    )
    
    # End of day in local time (next midnight)
    next_day = local_date + timedelta(days=1)
    local_end = tz.localize(
        datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0)
    )
    
    # Convert to UTC
    start_utc = local_start.astimezone(pytz.UTC)
    end_utc = local_end.astimezone(pytz.UTC)
    
    return (
        format_utc_iso8601(start_utc),
        format_utc_iso8601(end_utc),
    )


def compute_week_boundaries_utc(
    local_date: datetime,
    timezone_str: str = "UTC",
    start_on: int = 0,
) -> tuple[str, str]:
    """Compute UTC boundaries for a local week (Phase 7, Point 22).
    
    Handles DST transitions: a "week" may span DST spring/fall.
    
    Parameters
    ----------
    local_date
        Any date in the week
    timezone_str
        Timezone name
    start_on
        Day of week to start on (0=Monday, 6=Sunday)
        
    Returns
    -------
    tuple[str, str]
        (start_utc, end_utc) as ISO-8601 strings
        
    Examples
    --------
    >>> # Week containing DST transition
    >>> start, end = compute_week_boundaries_utc(
    ...     datetime(2025, 3, 9),  # Spring forward week
    ...     "America/New_York"
    ... )
    """
    tz = pytz.timezone(timezone_str)
    
    # Find start of week in local time
    week_start = get_week_start(local_date, start_on=start_on)
    local_start = tz.localize(
        datetime(week_start.year, week_start.month, week_start.day, 0, 0, 0)
    )
    
    # End of week (7 days later, midnight)
    week_end = week_start + timedelta(days=7)
    local_end = tz.localize(
        datetime(week_end.year, week_end.month, week_end.day, 0, 0, 0)
    )
    
    # Convert to UTC
    start_utc = local_start.astimezone(pytz.UTC)
    end_utc = local_end.astimezone(pytz.UTC)
    
    return (
        format_utc_iso8601(start_utc),
        format_utc_iso8601(end_utc),
    )


def compute_month_boundaries_utc(
    local_date: datetime,
    timezone_str: str = "UTC",
) -> tuple[str, str]:
    """Compute UTC boundaries for a local month (Phase 7, Point 22).
    
    Handles DST transitions within the month.
    
    Parameters
    ----------
    local_date
        Any date in the month
    timezone_str
        Timezone name
        
    Returns
    -------
    tuple[str, str]
        (start_utc, end_utc) as ISO-8601 strings
    """
    tz = pytz.timezone(timezone_str)
    
    # Start of month in local time
    local_start = tz.localize(
        datetime(local_date.year, local_date.month, 1, 0, 0, 0)
    )
    
    # End of month (first day of next month)
    if local_date.month == 12:
        next_month = datetime(local_date.year + 1, 1, 1)
    else:
        next_month = datetime(local_date.year, local_date.month + 1, 1)
    
    local_end = tz.localize(
        datetime(next_month.year, next_month.month, next_month.day, 0, 0, 0)
    )
    
    # Convert to UTC
    start_utc = local_start.astimezone(pytz.UTC)
    end_utc = local_end.astimezone(pytz.UTC)
    
    return (
        format_utc_iso8601(start_utc),
        format_utc_iso8601(end_utc),
    )


def compute_boundaries_utc(
    local_date: datetime,
    window: TimeWindow,
    timezone_str: str = "UTC",
    week_start_on: int = 0,
) -> tuple[str, str]:
    """Compute UTC boundaries for any time window.
    
    Convenience function that dispatches to specific window functions.
    
    Parameters
    ----------
    local_date
        Date in the window
    window
        Type of window ("day", "week", "month")
    timezone_str
        Timezone name
    week_start_on
        Day of week to start on (for week windows)
        
    Returns
    -------
    tuple[str, str]
        (start_utc, end_utc) as ISO-8601 strings
    """
    if window == "day":
        return compute_day_boundaries_utc(local_date, timezone_str)
    elif window == "week":
        return compute_week_boundaries_utc(local_date, timezone_str, week_start_on)
    elif window == "month":
        return compute_month_boundaries_utc(local_date, timezone_str)
    else:
        raise ValueError(f"Unknown window type: {window}")
