# ADR-005: UTC Time Discipline

## Status

**Accepted** (Phase 0, Point 3)

## Context

Time handling is complex:

- **Timezones**: Users in different zones
- **DST transitions**: Clocks jump forward/back
- **Persistence**: What format to store?
- **Display**: What timezone to show?
- **Calculations**: Day/week boundaries vary by timezone

Without discipline:
- Mixed local/UTC timestamps
- DST bugs (23 or 25-hour days)
- Comparison errors (can't compare mixed timezones)
- Migration nightmares

**Requirement**: Consistent, unambiguous time handling.

## Decision

### UTC Core Principle

**All timestamps stored in UTC. Always.**

```
┌─────────────────┐
│  Local Time     │ ← Display only (user-facing)
│  (e.g., CEST)   │
└────────┬────────┘
         │ Convert on display
         ▼
┌─────────────────┐
│  UTC (Storage)  │ ← Persistence layer
│  Always +00:00  │
└────────┬────────┘
         │ Convert on input
         ▲
┌─────────────────┐
│  Local Time     │ ← Input only (user-provided)
│  (Various TZ)   │
└─────────────────┘
```

### Rules

1. **Store UTC**: All timestamps in files are UTC ISO-8601
2. **Convert on edges**: Local→UTC on input, UTC→Local on display
3. **DST awareness**: Use `pytz` for correct conversions
4. **No naked datetimes**: Always timezone-aware
5. **ISO-8601 format**: `YYYY-MM-DDTHH:MM:SS+00:00`

### Time Windows

When computing day/week boundaries:

```python
# Compute UTC boundaries from local time
local_date = datetime(2025, 3, 9)  # DST transition day
start_utc, end_utc = compute_day_boundaries_utc(
    local_date,
    timezone_str="America/New_York"
)
# Returns: [2025-03-09T05:00:00+00:00, 2025-03-10T04:00:00+00:00)
# (23-hour day due to spring forward)
```

## Consequences

### Positive

- **Consistency**: One canonical time representation
- **Correctness**: No DST bugs from naive handling
- **Comparability**: Can always compare timestamps
- **Migration**: Clear target format
- **International**: Works for all timezones

### Negative

- **Conversion overhead**: Must convert on display
- **User confusion**: Stored times don't match wall clock
- **Complexity**: Proper timezone handling is non-trivial

### DST Handling

**Example: Spring Forward (23-hour day)**

```python
# March 9, 2025: 2am EST → 3am EDT
start_utc, end_utc = compute_day_boundaries_utc(
    datetime(2025, 3, 9),
    "America/New_York"
)
duration = (parse_utc_iso8601(end_utc) - parse_utc_iso8601(start_utc)).total_seconds() / 3600
assert duration == 23.0  # 23-hour day ✓
```

## Implementation

### Time Utilities

```python
# src/kira/core/time.py

def get_current_utc() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

def parse_utc_iso8601(timestamp: str) -> datetime:
    """Parse ISO-8601 UTC timestamp."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

def format_utc_iso8601(dt: datetime) -> str:
    """Format as ISO-8601 UTC."""
    return dt.astimezone(timezone.utc).isoformat()

def localize_to_timezone(utc_dt: datetime, tz_str: str) -> datetime:
    """Convert UTC to local timezone."""
    tz = pytz.timezone(tz_str)
    return utc_dt.astimezone(tz)
```

### Window Calculations

```python
# src/kira/rollups/time_windows.py

def compute_day_boundaries_utc(
    local_date: datetime,
    timezone_str: str = "UTC",
) -> tuple[str, str]:
    """Compute UTC boundaries for local day.
    
    Handles DST: day may be 23, 24, or 25 hours.
    """
    tz = pytz.timezone(timezone_str)
    
    # Start of day in local time
    local_start = tz.localize(
        datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0)
    )
    
    # End of day (next midnight)
    next_day = local_date + timedelta(days=1)
    local_end = tz.localize(
        datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0)
    )
    
    # Convert to UTC
    start_utc = local_start.astimezone(pytz.UTC)
    end_utc = local_end.astimezone(pytz.UTC)
    
    return (format_utc_iso8601(start_utc), format_utc_iso8601(end_utc))
```

## Verification

### DoD Check

```python
def test_no_local_times_persist():
    """Test DoD: No local times in files."""
    # All timestamps must be UTC
    doc = read_markdown(file_path)
    for field in ["created", "updated", "due"]:
        if field in doc.frontmatter:
            ts = doc.frontmatter[field]
            assert "+00:00" in ts or ts.endswith("Z")

def test_dst_transitions_covered():
    """Test DoD: Unit tests cover DST transitions."""
    # Spring forward (23-hour day)
    start, end = compute_day_boundaries_utc(
        datetime(2025, 3, 9),
        "America/New_York"
    )
    duration = (parse_utc_iso8601(end) - parse_utc_iso8601(start)).total_seconds() / 3600
    assert duration == 23.0
    
    # Fall back (25-hour day)
    start, end = compute_day_boundaries_utc(
        datetime(2025, 11, 2),
        "America/New_York"
    )
    duration = (parse_utc_iso8601(end) - parse_utc_iso8601(start)).total_seconds() / 3600
    assert duration == 25.0
```

### Tests

- `tests/unit/test_time.py`: Time utilities
- `tests/unit/test_time_windows.py`: DST-aware boundaries (20 tests)
- `tests/unit/test_rollup_aggregator.py`: Rollup with DST

## References

- Implementation: `src/kira/core/time.py`, `src/kira/rollups/time_windows.py`
- Related: ADR-002 (YAML Schema), ADR-004 (Event Envelope)
