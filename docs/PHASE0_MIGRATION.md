# Phase 0 Migration Guide

This document tracks the migration to Phase 0 requirements.

## Point 1: Single Writer via Host API - STATUS: Infrastructure Complete

### What's Done

- ✅ Created `src/storage/vault.py` with:
  - `get(uid)` - read entity by UID
  - `upsert(entity)` - create or update entity with file locking
  - `delete(uid)` - delete entity with file locking
  - `atomic_write()` - atomic file write helper with fsync
  - Per-entity file locking using `fcntl`
  
- ✅ All writes route through: `Vault.upsert → HostAPI.upsert_entity → md_io.write_markdown(atomic=True)`

- ✅ Atomic writes implemented with:
  - Write to `*.tmp` file
  - `fsync(tmp)` to flush data
  - Atomic `rename(tmp→real)`
  - `fsync(dir)` to persist rename

- ✅ Per-entity file locks prevent concurrent write conflicts

- ✅ Comprehensive tests in `tests/unit/test_vault_storage.py`

### What Needs Migration

The following files still use direct `open(..., 'w')` and need to be updated to use `Vault.upsert()`:

#### High Priority (Entity Mutations)
- [ ] `src/kira/cli/kira_task.py` - Task CRUD operations
- [ ] `src/kira/cli/kira_note.py` - Note CRUD operations  
- [ ] `src/kira/cli/kira_project.py` - Project CRUD operations
- [ ] `src/kira/cli/kira_context.py` - Context management
- [ ] `src/kira/cli/kira_links.py` - Link updates

#### Medium Priority (Plugin Storage)
- [ ] `src/kira/plugins/inbox/clarification_queue.py` - Should use Vault API
- [ ] `src/kira/plugins/inbox/src/kira_plugin_inbox/plugin.py` - Should use Vault API
- [ ] `src/kira/plugins/calendar/src/kira_plugin_calendar/plugin.py` - Should use Vault API

#### Low Priority (System Files - OK to keep direct writes)
- ✅ `src/kira/storage/vault.py` - This IS the write layer
- ✅ `src/kira/core/config.py` - Writes config files (not entities)
- ✅ `src/kira/core/ids.py` - Writes alias cache (not entities)
- ✅ `src/kira/core/vault_init.py` - Initializes schemas (not entities)
- ✅ `src/kira/cli/kira_backup.py` - Writes backup metadata (not entities)

### Migration Pattern

**Before:**
```python
# OLD: Direct write
with open(task_path, 'w', encoding='utf-8') as f:
    f.write(content)
```

**After:**
```python
# NEW: Through Vault layer
from kira.storage.vault import get_vault

vault = get_vault()
entity = vault.upsert(
    entity_type="task",
    data={"title": "My Task", "status": "todo"},
    content="Task description"
)
```

### Verification

Run this command to check for violations:
```bash
grep -r "open(.*'w" src/kira/cli/ src/kira/plugins/
```

## Point 2: Strict YAML Front-matter Schema - STATUS: Complete

### What's Done

- ✅ Created `src/kira/core/yaml_serializer.py` with:
  - `serialize_frontmatter()` - deterministic YAML serialization
  - `parse_frontmatter()` - parse YAML with validation
  - `normalize_timestamps_to_utc()` - ensure all timestamps are UTC
  - `get_canonical_key_order()` - fixed key ordering for consistency
  - `validate_strict_schema()` - enforce required fields

- ✅ Deterministic serialization features:
  - Fixed key ordering per `CANONICAL_KEY_ORDER`
  - ISO-8601 UTC timestamps enforced
  - Consistent quoting and formatting
  - Round-trip guarantee: serialize → parse → serialize = identical output

- ✅ Required schema keys enforced:
  - `uid` (or `id`)
  - `title`
  - `created_ts` (or `created`)
  - `updated_ts` (or `updated`)  
  - `state` (or `status` for tasks)
  - `tags[]` (must be list)

- ✅ Optional schema keys supported:
  - `due_ts`, `due_date`
  - `links[]`, `relates_to[]`, `depends_on[]`
  - `x-kira{}` (sync metadata for Phase 4)
  - Custom fields appear alphabetically after canonical fields

- ✅ Integrated with `md_io.py`:
  - `MarkdownDocument.to_markdown_string()` uses deterministic serializer
  - `parse_markdown()` uses deterministic parser
  - All vault operations now produce consistent YAML

- ✅ Comprehensive tests in `tests/unit/test_yaml_serializer.py`:
  - 17 tests covering deterministic serialization
  - Round-trip tests for Task, Note, Event entities
  - Special character handling
  - Nested dict support (x-kira metadata)
  - Timestamp normalization
  - Schema validation

### DoD Status

✅ Strict schema defined with required keys  
✅ Deterministic serialization (key order, quoting, ISO-8601 UTC)  
✅ Round-trip tests pass: serialize→parse→serialize yields identical output  
✅ Integration with existing Vault operations  
✅ All 26 tests passing (vault storage + YAML serializer)

## Point 3: UTC Time Discipline - STATUS: Complete

### What's Done

- ✅ Enhanced `src/kira/core/time.py` with UTC discipline helpers:
  - `get_current_utc()` - Always get time in UTC
  - `format_utc_iso8601()` - Format datetime as ISO-8601 UTC
  - `parse_utc_iso8601()` - Parse ISO-8601 to UTC datetime
  - `localize_utc_to_tz()` - Convert UTC to local timezone for display
  - `get_day_window_utc()` - Day boundaries in UTC with DST awareness
  - `get_week_window_utc()` - Week boundaries in UTC with DST awareness
  - `is_dst_transition_day()` - Detect DST transitions

- ✅ UTC Discipline Principles:
  - All timestamps stored as UTC (ISO-8601 format)
  - No local times persist in files
  - Localization only for display (--tz flag)
  - Format: `2025-10-08T12:30:00+00:00`

- ✅ DST Awareness:
  - `DayWindow` dataclass for day boundaries with DST flag
  - `WeekWindow` dataclass for week boundaries with DST flag
  - Correct handling of 23-hour days (spring forward)
  - Correct handling of 25-hour days (fall back)
  - Day/week windows account for DST transitions

- ✅ Timezone Localization:
  - Store: Always UTC
  - Display: Localize with `localize_utc_to_tz()`
  - Round-trip: format→parse→format yields identical UTC

- ✅ Comprehensive tests in `tests/unit/test_time_utc_discipline.py`:
  - 22 tests covering UTC discipline
  - DST spring forward tests (23-hour day)
  - DST fall back tests (25-hour day)
  - Week windows with DST transitions
  - Multiple timezones (Europe, US)
  - Round-trip formatting verification

### DoD Status

✅ ISO-8601 UTC parse/format helpers implemented  
✅ --tz localization for display (storage always UTC)  
✅ Day/week window math with DST awareness  
✅ Unit tests cover DST transitions (spring/fall)  
✅ No local times persist in files (enforced by format_utc_iso8601)

