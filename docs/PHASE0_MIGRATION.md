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

## Point 2: Strict YAML Front-matter Schema - STATUS: In Progress

TODO: Document after implementation

## Point 3: UTC Time Discipline - STATUS: Pending

TODO: Document after implementation

