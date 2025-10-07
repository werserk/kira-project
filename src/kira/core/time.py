"""Time and timezone utilities for Kira (ADR-008).

Provides consistent timezone handling across the system with configurable
default timezone for ID generation and timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

__all__ = [
    "TimeConfig",
    "format_datetime_for_id",
    "get_current_time",
    "get_default_timezone",
    "parse_datetime",
    "set_default_timezone",
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

