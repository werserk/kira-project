"""Time and timezone utilities for Kira (ADR-008, Phase 0 Point 3).

Provides consistent timezone handling across the system with:
- UTC discipline: all timestamps stored as UTC
- ISO-8601 format enforcement
- Timezone localization for display
- Day/week window calculations with DST awareness
- No local times persist in files
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

__all__ = [
    "TimeConfig",
    "DayWindow",
    "WeekWindow",
    "format_datetime_for_id",
    "format_utc_iso8601",
    "parse_utc_iso8601",
    "get_current_time",
    "get_current_utc",
    "get_default_timezone",
    "parse_datetime",
    "set_default_timezone",
    "localize_utc_to_tz",
    "get_day_window_utc",
    "get_week_window_utc",
    "is_dst_transition_day",
]


class TimeConfig:
    """Global time configuration."""

    _default_timezone = "Europe/Brussels"  # ADR-008 default

    @classmethod
    def get_default_timezone_name(cls) -> str:
        """Get default timezone name.

        Returns
        -------
        str
            Timezone name (e.g., "Europe/Brussels")
        """
        return cls._default_timezone

    @classmethod
    def set_default_timezone_name(cls, timezone_name: str) -> None:
        """Set default timezone.

        Parameters
        ----------
        timezone_name
            IANA timezone name (e.g., "Europe/Brussels", "America/New_York")

        Raises
        ------
        ValueError
            If timezone is invalid
        """
        # Validate timezone
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:
            raise ValueError(f"Invalid timezone: {timezone_name}") from exc

        cls._default_timezone = timezone_name


def get_default_timezone() -> ZoneInfo:
    """Get default timezone object.

    Returns
    -------
    ZoneInfo
        Default timezone
    """
    return ZoneInfo(TimeConfig.get_default_timezone_name())


def set_default_timezone(timezone_name: str) -> None:
    """Set default timezone for the system.

    Parameters
    ----------
    timezone_name
        IANA timezone name

    Raises
    ------
    ValueError
        If timezone is invalid
    """
    TimeConfig.set_default_timezone_name(timezone_name)


def get_current_time(tz: ZoneInfo | str | None = None) -> datetime:
    """Get current time in specified timezone.

    Parameters
    ----------
    tz
        Timezone (ZoneInfo, timezone name string, or None for default)

    Returns
    -------
    datetime
        Current time in specified timezone
    """
    if tz is None:
        tz = get_default_timezone()
    elif isinstance(tz, str):
        tz = ZoneInfo(tz)

    return datetime.now(tz)


def format_datetime_for_id(dt: datetime | None = None, tz: ZoneInfo | str | None = None) -> str:
    """Format datetime for entity ID (ADR-008).

    Format: YYYYMMDD-HHmm
    Example: 20250115-1430 (January 15, 2025, 14:30)

    Parameters
    ----------
    dt
        Datetime to format (default: now)
    tz
        Timezone (default: system default)

    Returns
    -------
    str
        Formatted datetime string
    """
    if dt is None:
        dt = get_current_time(tz)
    elif tz is not None:
        # Convert to specified timezone
        if isinstance(tz, str):
            tz = ZoneInfo(tz)
        dt = dt.astimezone(tz)

    # Format: YYYYMMDD-HHmm
    return dt.strftime("%Y%m%d-%H%M")


def parse_datetime(dt_str: str, tz: ZoneInfo | str | None = None) -> datetime:
    """Parse datetime string.

    Supports:
    - ISO 8601: 2025-01-15T14:30:00Z or 2025-01-15T14:30:00+01:00
    - ID format: 20250115-1430

    Parameters
    ----------
    dt_str
        Datetime string
    tz
        Timezone for ID format (default: system default)

    Returns
    -------
    datetime
        Parsed datetime

    Raises
    ------
    ValueError
        If parsing fails
    """
    # Try ISO 8601 first
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    # Try ID format: YYYYMMDD-HHmm
    import re

    match = re.match(r"^(\d{8})-(\d{4})$", dt_str)
    if match:
        date_part, time_part = match.groups()

        year = int(date_part[0:4])
        month = int(date_part[4:6])
        day = int(date_part[6:8])
        hour = int(time_part[0:2])
        minute = int(time_part[2:4])

        if tz is None:
            tz = get_default_timezone()
        elif isinstance(tz, str):
            tz = ZoneInfo(tz)

        return datetime(year, month, day, hour, minute, 0, 0, tzinfo=tz)

    raise ValueError(f"Cannot parse datetime: {dt_str}")


def format_datetime_iso(dt: datetime) -> str:
    """Format datetime as ISO 8601 string.

    Parameters
    ----------
    dt
        Datetime to format

    Returns
    -------
    str
        ISO 8601 formatted string
    """
    return dt.isoformat()


def now_in_timezone(timezone_name: str) -> datetime:
    """Get current time in specific timezone.

    Parameters
    ----------
    timezone_name
        IANA timezone name

    Returns
    -------
    datetime
        Current time in timezone
    """
    return datetime.now(ZoneInfo(timezone_name))


def convert_timezone(dt: datetime, to_tz: str | ZoneInfo) -> datetime:
    """Convert datetime to different timezone.

    Parameters
    ----------
    dt
        Datetime to convert
    to_tz
        Target timezone

    Returns
    -------
    datetime
        Converted datetime
    """
    if isinstance(to_tz, str):
        to_tz = ZoneInfo(to_tz)

    return dt.astimezone(to_tz)


def ensure_timezone(dt: datetime, tz: str | ZoneInfo | None = None) -> datetime:
    """Ensure datetime has timezone information.

    Parameters
    ----------
    dt
        Datetime (may be naive)
    tz
        Timezone to assume if dt is naive (default: UTC)

    Returns
    -------
    datetime
        Timezone-aware datetime
    """
    if dt.tzinfo is not None:
        return dt

    # Naive datetime - assume timezone
    if tz is None:
        tz_obj: tzinfo = timezone.utc
    elif isinstance(tz, str):
        tz_obj = ZoneInfo(tz)
    else:
        tz_obj = tz

    return dt.replace(tzinfo=tz_obj)


def load_timezone_from_config(config: dict[str, Any]) -> None:
    """Load and set timezone from configuration.

    Parameters
    ----------
    config
        Configuration dictionary (from kira.yaml)
    """
    tz_name = config.get("vault", {}).get("tz")

    if tz_name:
        try:
            set_default_timezone(tz_name)
        except ValueError as exc:
            # Fall back to default if invalid
            print(f"Warning: Invalid timezone '{tz_name}': {exc}")
            print(f"Using default: {TimeConfig.get_default_timezone_name()}")


# ============================================================================
# Phase 0, Point 3: UTC Discipline Helpers
# ============================================================================

from dataclasses import dataclass


@dataclass(frozen=True)
class DayWindow:
    """UTC time window for a day in a specific timezone.

    Represents [start_utc, end_utc) for a calendar day in a timezone,
    accounting for DST transitions.

    Attributes
    ----------
    start_utc : datetime
        Start of day in UTC (inclusive)
    end_utc : datetime
        End of day in UTC (exclusive)
    local_date : str
        Local date (YYYY-MM-DD)
    timezone_name : str
        IANA timezone name
    has_dst_transition : bool
        Whether this day includes a DST transition
    """

    start_utc: datetime
    end_utc: datetime
    local_date: str
    timezone_name: str
    has_dst_transition: bool = False


@dataclass(frozen=True)
class WeekWindow:
    """UTC time window for a week in a specific timezone.

    Represents [start_utc, end_utc) for a calendar week (Monday-Sunday)
    in a timezone, accounting for DST transitions.

    Attributes
    ----------
    start_utc : datetime
        Start of week (Monday 00:00) in UTC (inclusive)
    end_utc : datetime
        End of week (Monday 00:00 next week) in UTC (exclusive)
    week_start_date : str
        Local date of week start (YYYY-MM-DD)
    timezone_name : str
        IANA timezone name
    has_dst_transition : bool
        Whether this week includes a DST transition
    """

    start_utc: datetime
    end_utc: datetime
    week_start_date: str
    timezone_name: str
    has_dst_transition: bool = False


def get_current_utc() -> datetime:
    """Get current time in UTC.

    Phase 0, Point 3: Always store times in UTC.

    Returns
    -------
    datetime
        Current time in UTC with timezone info

    Example
    -------
    >>> now_utc = get_current_utc()
    >>> now_utc.tzinfo
    datetime.timezone.utc
    """
    return datetime.now(timezone.utc)


def format_utc_iso8601(dt: datetime) -> str:
    """Format datetime as ISO-8601 UTC string.

    Phase 0, Point 3: Enforce ISO-8601 UTC format for persistence.
    Always converts to UTC before formatting.

    Parameters
    ----------
    dt
        Datetime to format (with or without timezone)

    Returns
    -------
    str
        ISO-8601 UTC string (e.g., "2025-10-08T12:30:00+00:00")

    Example
    -------
    >>> from datetime import datetime, timezone
    >>> dt = datetime(2025, 10, 8, 12, 30, 0, tzinfo=timezone.utc)
    >>> format_utc_iso8601(dt)
    '2025-10-08T12:30:00+00:00'
    """
    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat()


def parse_utc_iso8601(iso_string: str) -> datetime:
    """Parse ISO-8601 string to UTC datetime.

    Phase 0, Point 3: Parse and convert to UTC.

    Parameters
    ----------
    iso_string
        ISO-8601 formatted string

    Returns
    -------
    datetime
        Datetime in UTC

    Raises
    ------
    ValueError
        If string is not valid ISO-8601

    Example
    -------
    >>> dt = parse_utc_iso8601("2025-10-08T14:30:00+02:00")
    >>> dt.hour  # Converted to UTC
    12
    """
    # Handle 'Z' suffix (Zulu time = UTC)
    iso_string = iso_string.replace("Z", "+00:00")

    dt = datetime.fromisoformat(iso_string)

    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    return dt


def localize_utc_to_tz(utc_dt: datetime, tz: str | ZoneInfo) -> datetime:
    """Convert UTC datetime to specific timezone for display.

    Phase 0, Point 3: Localize for --tz display.

    Parameters
    ----------
    utc_dt
        UTC datetime
    tz
        Target timezone (name or ZoneInfo)

    Returns
    -------
    datetime
        Datetime in target timezone

    Example
    -------
    >>> utc_dt = datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
    >>> local_dt = localize_utc_to_tz(utc_dt, "Europe/Brussels")
    >>> local_dt.hour  # Brussels is UTC+2 in summer
    14
    """
    if isinstance(tz, str):
        tz = ZoneInfo(tz)

    # Ensure UTC
    if utc_dt.tzinfo != timezone.utc:
        utc_dt = utc_dt.astimezone(timezone.utc)

    return utc_dt.astimezone(tz)


def get_day_window_utc(date_str: str, tz: str | ZoneInfo | None = None) -> DayWindow:
    """Get UTC time window for a calendar day in a timezone.

    Phase 0, Point 3: Day/week window math with DST awareness.

    Computes [start_utc, end_utc) for the given calendar day in the
    specified timezone, properly handling DST transitions.

    Parameters
    ----------
    date_str
        Date in YYYY-MM-DD format
    tz
        Timezone (name, ZoneInfo, or None for default)

    Returns
    -------
    DayWindow
        UTC window for the calendar day

    Example
    -------
    >>> window = get_day_window_utc("2025-10-08", "Europe/Brussels")
    >>> window.start_utc  # 2025-10-07T22:00:00+00:00 (midnight Brussels time)
    >>> window.end_utc    # 2025-10-08T22:00:00+00:00 (next midnight)
    """
    if tz is None:
        tz = get_default_timezone()
    elif isinstance(tz, str):
        tz = ZoneInfo(tz)

    # Parse date
    from datetime import date

    local_date = date.fromisoformat(date_str)

    # Create local midnight datetime
    local_start = datetime.combine(local_date, datetime.min.time(), tzinfo=tz)
    local_end = local_start + timedelta(days=1)

    # Convert to UTC
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)

    # Check for DST transition
    has_dst = is_dst_transition_day(local_date, tz)

    return DayWindow(
        start_utc=start_utc,
        end_utc=end_utc,
        local_date=date_str,
        timezone_name=str(tz),
        has_dst_transition=has_dst,
    )


def get_week_window_utc(week_start_date: str, tz: str | ZoneInfo | None = None) -> WeekWindow:
    """Get UTC time window for a calendar week in a timezone.

    Phase 0, Point 3: Week window math with DST awareness.

    Computes [start_utc, end_utc) for the week starting on the given
    Monday, properly handling DST transitions.

    Parameters
    ----------
    week_start_date
        Monday date in YYYY-MM-DD format
    tz
        Timezone (name, ZoneInfo, or None for default)

    Returns
    -------
    WeekWindow
        UTC window for the calendar week

    Raises
    ------
    ValueError
        If date is not a Monday

    Example
    -------
    >>> window = get_week_window_utc("2025-10-06", "Europe/Brussels")  # Monday
    >>> window.start_utc  # Monday 00:00 Brussels in UTC
    >>> window.end_utc    # Next Monday 00:00 Brussels in UTC
    """
    if tz is None:
        tz = get_default_timezone()
    elif isinstance(tz, str):
        tz = ZoneInfo(tz)

    # Parse date
    from datetime import date

    local_date = date.fromisoformat(week_start_date)

    # Verify it's a Monday (weekday() == 0)
    if local_date.weekday() != 0:
        raise ValueError(f"Date {week_start_date} is not a Monday (weekday={local_date.weekday()})")

    # Create local midnight datetime for week start and end
    local_start = datetime.combine(local_date, datetime.min.time(), tzinfo=tz)
    local_end = local_start + timedelta(days=7)

    # Convert to UTC
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)

    # Check for DST transition during the week
    has_dst = False
    for day_offset in range(7):
        day = local_date + timedelta(days=day_offset)
        if is_dst_transition_day(day, tz):
            has_dst = True
            break

    return WeekWindow(
        start_utc=start_utc,
        end_utc=end_utc,
        week_start_date=week_start_date,
        timezone_name=str(tz),
        has_dst_transition=has_dst,
    )


def is_dst_transition_day(date_obj: Any, tz: ZoneInfo) -> bool:
    """Check if a date includes a DST transition.

    Phase 0, Point 3: DST awareness for time windows.

    Parameters
    ----------
    date_obj
        Date to check (datetime.date or datetime)
    tz
        Timezone to check

    Returns
    -------
    bool
        True if this date includes a DST transition

    Example
    -------
    >>> from datetime import date
    >>> from zoneinfo import ZoneInfo
    >>> # March 2025 DST transition in Europe
    >>> tz = ZoneInfo("Europe/Brussels")
    >>> is_dst_transition_day(date(2025, 3, 30), tz)  # DST starts
    True
    >>> is_dst_transition_day(date(2025, 10, 26), tz)  # DST ends
    True
    >>> is_dst_transition_day(date(2025, 10, 8), tz)   # Regular day
    False
    """
    from datetime import date as date_type

    # Extract date if datetime
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    elif not isinstance(date_obj, date_type):
        raise TypeError(f"Expected date or datetime, got {type(date_obj)}")

    # Create two datetimes for this day
    start_of_day = datetime.combine(date_obj, datetime.min.time(), tzinfo=tz)
    end_of_day = start_of_day + timedelta(hours=23)

    # Check if DST offset changes during the day
    start_dst = start_of_day.dst()
    end_dst = end_of_day.dst()

    return start_dst != end_dst
