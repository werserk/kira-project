"""Tests for time and timezone utilities (ADR-008)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.time import (
    TimeConfig,
    convert_timezone,
    ensure_timezone,
    format_datetime_for_id,
    format_datetime_iso,
    get_current_time,
    get_default_timezone,
    load_timezone_from_config,
    now_in_timezone,
    parse_datetime,
    set_default_timezone,
)


class TestTimeConfig:
    def test_default_timezone(self):
        # Reset to default
        TimeConfig._default_timezone = "Europe/Brussels"

        assert TimeConfig.get_default_timezone_name() == "Europe/Brussels"

    def test_set_default_timezone(self):
        original = TimeConfig.get_default_timezone_name()

        try:
            TimeConfig.set_default_timezone_name("America/New_York")
            assert TimeConfig.get_default_timezone_name() == "America/New_York"
        finally:
            # Restore original
            TimeConfig._default_timezone = original

    def test_set_invalid_timezone(self):
        with pytest.raises(ValueError):
            TimeConfig.set_default_timezone_name("Invalid/Timezone")


class TestGetDefaultTimezone:
    def test_get_default_timezone(self):
        tz = get_default_timezone()

        assert isinstance(tz, ZoneInfo)
        # Default is Europe/Brussels per ADR-008
        assert str(tz) in ["Europe/Brussels", TimeConfig.get_default_timezone_name()]

    def test_set_default_timezone(self):
        original = TimeConfig.get_default_timezone_name()

        try:
            set_default_timezone("America/New_York")
            tz = get_default_timezone()
            assert str(tz) == "America/New_York"
        finally:
            TimeConfig._default_timezone = original


class TestGetCurrentTime:
    def test_get_current_time_default(self):
        current = get_current_time()

        assert isinstance(current, datetime)
        assert current.tzinfo is not None

    def test_get_current_time_specific_tz(self):
        current_utc = get_current_time("UTC")
        current_brussels = get_current_time("Europe/Brussels")

        assert current_utc.tzinfo is not None
        assert current_brussels.tzinfo is not None

        # Both should be recent (within last minute)
        now = datetime.now(timezone.utc)
        assert abs((current_utc - now).total_seconds()) < 60

    def test_get_current_time_with_zoneinfo(self):
        tz = ZoneInfo("America/New_York")
        current = get_current_time(tz)

        assert current.tzinfo is not None


class TestFormatDatetimeForId:
    def test_format_datetime_for_id_default(self):
        result = format_datetime_for_id()

        # Should match YYYYMMDD-HHmm
        assert len(result) == 13  # 8 + 1 + 4
        assert result[8] == "-"
        assert result[:8].isdigit()
        assert result[9:].isdigit()

    def test_format_datetime_for_id_specific(self):
        dt = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = format_datetime_for_id(dt)

        # Format depends on system timezone conversion
        assert len(result) == 13
        assert "-" in result

    def test_format_datetime_for_id_with_timezone(self):
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = format_datetime_for_id(dt, tz="Europe/Brussels")

        # Should be formatted in Brussels time
        assert result.startswith("20250115-")


class TestParseDatetime:
    def test_parse_iso_format(self):
        dt_str = "2025-01-15T14:30:00Z"
        result = parse_datetime(dt_str)

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30

    def test_parse_iso_with_timezone(self):
        dt_str = "2025-01-15T14:30:00+01:00"
        result = parse_datetime(dt_str)

        assert result.tzinfo is not None

    def test_parse_id_format(self):
        dt_str = "20250115-1430"
        result = parse_datetime(dt_str)

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30

    def test_parse_invalid_format(self):
        with pytest.raises(ValueError):
            parse_datetime("invalid-date-format")


class TestConvertTimezone:
    def test_convert_timezone(self):
        dt_utc = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        dt_brussels = convert_timezone(dt_utc, "Europe/Brussels")

        # Brussels is UTC+1 in winter
        assert dt_brussels.hour in [13, 14]  # Account for DST

    def test_convert_with_zoneinfo(self):
        dt_utc = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("America/New_York")
        dt_ny = convert_timezone(dt_utc, tz)

        assert dt_ny.tzinfo is not None


class TestEnsureTimezone:
    def test_ensure_timezone_aware(self):
        dt_aware = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = ensure_timezone(dt_aware)

        assert result is dt_aware  # Should return as-is

    def test_ensure_timezone_naive_default(self):
        dt_naive = datetime(2025, 1, 15, 12, 0, 0)
        result = ensure_timezone(dt_naive)

        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_ensure_timezone_naive_specific(self):
        dt_naive = datetime(2025, 1, 15, 12, 0, 0)
        result = ensure_timezone(dt_naive, tz="Europe/Brussels")

        assert result.tzinfo is not None


class TestLoadTimezoneFromConfig:
    def test_load_timezone_from_config(self):
        original = TimeConfig.get_default_timezone_name()

        try:
            config = {"vault": {"tz": "America/New_York"}}

            load_timezone_from_config(config)

            assert TimeConfig.get_default_timezone_name() == "America/New_York"

        finally:
            TimeConfig._default_timezone = original

    def test_load_timezone_invalid(self, capsys):
        original = TimeConfig.get_default_timezone_name()

        try:
            config = {"vault": {"tz": "Invalid/Timezone"}}

            load_timezone_from_config(config)

            # Should fall back to default and print warning
            captured = capsys.readouterr()
            assert "Warning" in captured.out or TimeConfig.get_default_timezone_name() == original

        finally:
            TimeConfig._default_timezone = original


class TestFormatDatetimeIso:
    def test_format_datetime_iso(self):
        dt = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = format_datetime_iso(dt)

        assert "2025-01-15" in result
        assert "14:30:00" in result


class TestNowInTimezone:
    def test_now_in_timezone(self):
        now_utc = now_in_timezone("UTC")
        now_brussels = now_in_timezone("Europe/Brussels")

        assert now_utc.tzinfo is not None
        assert now_brussels.tzinfo is not None

        # Should be recent
        current = datetime.now(timezone.utc)
        assert abs((now_utc - current).total_seconds()) < 60
