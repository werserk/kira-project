# Phase 1 Implementation — Canonical Schema & Time Discipline

**Status:** ✅ COMPLETE  
**Date:** 2025-10-08  
**Branch:** dev

---

## Overview

Phase 1 establishes the canonical schema and time discipline for Kira by implementing:
1. YAML front-matter schema as source of truth (Point 3)
2. UTC time utilities with DST awareness (Point 4)

---

## 1. YAML Front-Matter Schema (Point 3)

### Implementation

**Files Modified:**
- `src/kira/core/yaml_serializer.py` — Enhanced with Phase 1 improvements
- `src/kira/core/validation.py` — Already enforces strict schema
- `tests/unit/test_schema_round_trip.py` — NEW: Comprehensive round-trip tests

### Canonical Entity Structure

#### Required Keys (All Entities):
```yaml
id: task-20251008-1200           # uid: Unique identifier
title: "Implement Phase 1"       # Task/Note/Event title
state: doing                     # or status: Entity state
created: 2025-10-08T10:00:00+00:00  # created_ts: ISO-8601 UTC
updated: 2025-10-08T12:00:00+00:00  # updated_ts: ISO-8601 UTC
tags: []                         # List of tags
```

#### Optional Keys:
```yaml
# Time-related
due_date: 2025-10-15T18:00:00+00:00   # ISO-8601 UTC
start_ts: 2025-10-08T12:00:00+00:00
done_ts: 2025-10-08T15:00:00+00:00

# Relationships
links: ["[[note-001]]"]
depends_on: ["task-002"]
relates_to: ["adr-001"]

# Kira sync metadata
x-kira:
  source: telegram
  version: 3
  remote_id: abc123
  last_write_ts: 2025-10-08T12:00:00+00:00
```

### Deterministic Serialization

#### Key Ordering
Keys are serialized in canonical order per `CANONICAL_KEY_ORDER`:
1. **Identity:** id, title
2. **Metadata:** type, status/state, priority
3. **Timestamps:** created, updated, due_date, start_time, end_time
4. **Classification:** tags, category
5. **Relationships:** relates_to, depends_on, blocks, links
6. **Optional:** description, assignee, estimate, etc.
7. **Sync:** x-kira
8. **Unknown keys:** Alphabetically after known keys

#### Timestamp Normalization
- All timestamps stored as **ISO-8601 UTC**
- Format: `YYYY-MM-DDTHH:MM:SS+00:00`
- Naive datetimes assumed to be UTC
- Local times converted to UTC before storage
- Nested timestamps (e.g., `x-kira.last_write_ts`) normalized

#### Special Character Handling
Strings requiring quoting (Phase 1, Point 3):
- Wiki-style links: `[[...]]`
- Strings starting with: `[`, `{`, `-`, or space
- Strings containing: `:`, `#`, `|`, `>`, `&`, `*`, `!`, `%`, `@`
- Multi-line strings

### Round-Trip Guarantee

**DoD:** serialize→parse→serialize yields identical YAML

Example:
```python
original = {
    "id": "task-001",
    "title": "Test",
    "status": "todo",
    "created": "2025-10-08T12:00:00+00:00",
    "updated": "2025-10-08T12:00:00+00:00",
    "tags": ["test"],
}

# First serialization
yaml1 = serialize_frontmatter(original)
parsed1 = parse_frontmatter(yaml1)

# Second serialization
yaml2 = serialize_frontmatter(parsed1)
parsed2 = parse_frontmatter(yaml2)

# Guarantee
assert yaml1 == yaml2  # Identical YAML strings
assert parsed1 == parsed2  # Identical parsed data
```

### Validation

Strict schema validation enforced at write boundary (via `validate_entity`):
- Required fields: id, title, state/status, created, updated, tags
- ISO-8601 UTC timestamps
- Tags must be a list
- Valid state transitions (Task FSM)

---

## 2. UTC Time Utilities (Point 4)

### Implementation

**File:** `src/kira/core/time.py` — Already comprehensive, verified in Phase 1  
**Tests:** `tests/unit/test_time_utc_discipline.py` — Complete DST coverage

### Core Functions

#### UTC Discipline
```python
# Get current UTC time
now_utc = get_current_utc()  # Always UTC

# Format for storage (ISO-8601 UTC)
iso_string = format_utc_iso8601(now_utc)  # "2025-10-08T12:30:00+00:00"

# Parse from storage
dt = parse_utc_iso8601(iso_string)  # datetime in UTC

# Localize for display only (never store)
local_dt = localize_utc_to_tz(now_utc, "Europe/Brussels")
```

#### Day/Week Windows with DST Awareness

```python
# Get UTC window for a calendar day
window = get_day_window_utc("2025-10-08", "Europe/Brussels")
# window.start_utc: 2025-10-07T22:00:00+00:00 (midnight Brussels in UTC)
# window.end_utc:   2025-10-08T22:00:00+00:00 (next midnight)
# window.has_dst_transition: False

# DST spring forward (23-hour day)
window = get_day_window_utc("2025-03-30", "Europe/Brussels")
# Duration: 23 hours (clocks skip from 02:00 to 03:00)

# DST fall back (25-hour day)
window = get_day_window_utc("2025-10-26", "Europe/Brussels")
# Duration: 25 hours (clocks go from 03:00 back to 02:00)

# Week window
window = get_week_window_utc("2025-10-06", "Europe/Brussels")  # Monday
# window.start_utc: Monday 00:00 Brussels in UTC
# window.end_utc:   Next Monday 00:00 Brussels in UTC
# window.has_dst_transition: True if week contains DST change
```

#### DST Transition Detection

```python
from datetime import date
from zoneinfo import ZoneInfo

tz = ZoneInfo("Europe/Brussels")

# Check if date includes DST transition
is_dst_transition_day(date(2025, 3, 30), tz)  # True (spring forward)
is_dst_transition_day(date(2025, 10, 26), tz)  # True (fall back)
is_dst_transition_day(date(2025, 10, 8), tz)   # False (regular day)
```

### Test Coverage

#### DST Boundary Tests (Phase 1, Point 4 DoD)

**Spring Forward (March 30, 2025):**
- Day is 23 hours long (loses 1 hour)
- `get_day_window_utc` correctly computes 23-hour duration
- `is_dst_transition_day` returns True

**Fall Back (October 26, 2025):**
- Day is 25 hours long (gains 1 hour)
- `get_day_window_utc` correctly computes 25-hour duration
- `is_dst_transition_day` returns True

**Week Windows:**
- Week containing DST transition flagged with `has_dst_transition=True`
- October 20-27 week: 169 hours (25-hour Sunday)

**Different Timezones:**
- US Eastern: March 9 (spring), November 2 (fall)
- Europe/Brussels: March 30 (spring), October 26 (fall)

#### Round-Trip UTC Formatting
```python
# Test format→parse→format yields identical result
original_dt = datetime(2025, 10, 8, 12, 30, 45, tzinfo=timezone.utc)
iso_str = format_utc_iso8601(original_dt)
parsed_dt = parse_utc_iso8601(iso_str)
iso_str2 = format_utc_iso8601(parsed_dt)

assert iso_str == iso_str2  # Identical strings
assert parsed_dt == original_dt  # Identical datetimes
```

---

## Test Results

### Phase 1 Test Suite

```bash
$ poetry run pytest tests/unit/test_schema_round_trip.py -v
# Result: 22 passed in 0.10s ✅

$ poetry run pytest tests/unit/test_time_utc_discipline.py -v
# Result: 22 passed in 0.08s ✅

$ poetry run pytest tests/unit/test_time.py -v
# Result: 24 passed in 0.04s ✅

# Total: 68 tests, 100% pass rate
```

### Coverage Breakdown

#### Schema Round-Trip Tests (22 tests):
- ✅ Deterministic serialization (2 tests)
- ✅ Timestamp normalization (4 tests)
- ✅ Task round-trip (3 tests)
- ✅ Note round-trip (2 tests)
- ✅ Event round-trip (2 tests)
- ✅ Strict schema validation (4 tests)
- ✅ Special characters (3 tests)
- ✅ Consistent output (2 tests)

#### UTC Time Discipline Tests (22 tests):
- ✅ UTC formatting/parsing (7 tests)
- ✅ Day windows (3 tests)
- ✅ Week windows (3 tests)
- ✅ DST transitions (6 tests)
- ✅ Round-trip guarantees (3 tests)

#### Time Utilities Tests (24 tests):
- ✅ Timezone configuration (8 tests)
- ✅ Current time operations (3 tests)
- ✅ Datetime formatting (4 tests)
- ✅ Timezone conversions (4 tests)
- ✅ Config loading (2 tests)
- ✅ ISO formatting (3 tests)

---

## Definition of Done ✅

### Point 3: YAML Front-Matter Schema
- [x] Required keys enforced: uid, title, created_ts, updated_ts, state, tags[]
- [x] Optional keys supported: due_ts, links[], x-kira{...}
- [x] Deterministic serialization with canonical key order
- [x] ISO-8601 UTC timestamps
- [x] Proper quoting for special characters (including [[...]])
- [x] **Round-trip tests pass:** serialize→parse→equal for all entities
- [x] 22 comprehensive round-trip tests (100% pass rate)

### Point 4: UTC Time Utilities
- [x] `src/core/time.py` complete with UTC discipline
- [x] parse/format ISO-8601 UTC
- [x] Localize via timezone for display only
- [x] Day/week window computation with DST awareness
- [x] **Unit tests cover DST transitions** (Spring/Fall for Europe & US)
- [x] DST boundary conditions tested (23-hour, 25-hour days)
- [x] 46 comprehensive time/UTC tests (100% pass rate)

---

## Integration with Existing Systems

### Validation Pipeline
```
Entity Write Request
    ↓
validate_entity(entity_type, data)
    ↓
validate_strict_schema(entity_type, data)  ← Phase 1 enforcement
    ↓
normalize_timestamps_to_utc(data)  ← Phase 1 UTC discipline
    ↓
serialize_frontmatter(data)  ← Phase 1 deterministic output
    ↓
HostAPI.upsert_entity() → vault.py → atomic write
```

### Time Handling
```
User Input (Local Time)
    ↓
parse/validate
    ↓
Convert to UTC ← Phase 1 discipline
    ↓
Store as ISO-8601 UTC ← Phase 1 format
    ↓
Retrieve from vault
    ↓
Parse UTC timestamp
    ↓
Localize for display (via --tz) ← Phase 1 localization
    ↓
Show to user (Local Time)
```

---

## Files Changed

```
Modified:
- src/kira/core/yaml_serializer.py  (+35 lines, enhanced Phase 1)
  * Fixed nested timestamp normalization (deep copy)
  * Added proper quoting for [[...]] and special chars
  * Enhanced list item serialization
  
Created:
- tests/unit/test_schema_round_trip.py  (+341 lines, NEW)
  * 22 comprehensive round-trip tests
  * Task/Note/Event entity tests
  * Deterministic serialization tests
  * Strict schema validation tests

Verified Existing:
- src/kira/core/time.py  (already complete)
- tests/unit/test_time_utc_discipline.py  (22 tests)
- tests/unit/test_time.py  (24 tests)
- src/kira/core/validation.py  (already enforces schema)
```

---

## Benefits Delivered

### 1. Data Consistency
- All entities use canonical schema
- Round-trip guarantee prevents data loss
- Deterministic output enables git-friendly diffs

### 2. Time Correctness
- No ambiguous timestamps
- DST transitions handled correctly
- Week/day boundaries accurate across timezones

### 3. Testability
- 68 comprehensive tests
- 100% pass rate
- DST edge cases covered

### 4. Maintainability
- Single source of truth for schema
- Clear validation errors
- Predictable serialization

---

## Next Steps: Phase 2

With Phase 1 complete, the foundation is ready for:
- **Task FSM with guards** (Phase 2, Point 5)
- **Validation at write boundary** (Phase 2, Point 6)
- **Quarantine for bad inputs** (Phase 2, Point 7)

---

## Phase 1 Checklist

### Point 3: YAML Schema
- [x] Entities: Task, Note, Event
- [x] Required keys: uid, title, created_ts, updated_ts, state, tags[]
- [x] Optional: due_ts, links[], x-kira{...}
- [x] Deterministic serialization
- [x] Canonical key order
- [x] ISO-8601 UTC timestamps
- [x] Special character quoting
- [x] Round-trip tests pass (22/22)

### Point 4: UTC Time Utilities
- [x] src/core/time.py implemented
- [x] parse/format ISO-8601 UTC
- [x] Localize via --tz
- [x] Day/week windows with DST awareness
- [x] DST transition detection
- [x] Unit tests cover DST (46/46 pass)
- [x] Europe/Brussels spring forward (March 30)
- [x] Europe/Brussels fall back (October 26)
- [x] US Eastern DST transitions
- [x] 23-hour and 25-hour day handling

---

**Phase 1 Status:** ✅ **COMPLETE & TESTED**  
**Test Pass Rate:** 68/68 (100%)  
**Ready for:** Phase 2 (Task FSM & Domain Validation)

