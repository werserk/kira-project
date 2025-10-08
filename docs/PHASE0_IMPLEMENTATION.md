# Phase 0 Implementation — Runtime Flags & Single Writer Pattern

**Status:** ✅ COMPLETE  
**Date:** 2025-10-08  
**Branch:** dev

---

## Overview

Phase 0 establishes the foundation for Kira's alpha release by implementing:
1. Runtime mode flags and feature toggles (all integrations OFF by default)
2. Single Writer pattern for all vault entity mutations

---

## 1. Runtime Flags & Defaults (Point 1)

### Implementation

**File:** `src/kira/config/settings.py`

Added the following environment variables:

```bash
# Phase 0 Runtime Mode
KIRA_MODE=alpha                    # Runtime mode: alpha, beta, stable

# Core Settings
KIRA_VAULT_PATH=vault              # Required: Path to vault directory
KIRA_DEFAULT_TZ=Europe/Brussels    # Default timezone (UTC if not set)

# Phase 0 Feature Flags (ALL OFF BY DEFAULT)
KIRA_ENABLE_GCAL=false            # Google Calendar integration
KIRA_ENABLE_TELEGRAM=false        # Telegram adapter
KIRA_ENABLE_PLUGINS=false         # Plugin system
```

### Settings Dataclass

Updated `Settings` dataclass with:
- `mode: str = "alpha"` — Runtime mode flag
- `enable_gcal: bool = False` — GCal integration toggle
- `enable_telegram: bool = False` — Telegram integration toggle
- `enable_plugins: bool = False` — Plugin system toggle

### Configuration Files Updated

1. **config/env.example** — Updated with Phase 0 structure
2. **src/kira/config/settings.py** — Added new fields and parsing logic
3. **generate_example_env()** — Updated to reflect Phase 0 requirements

### Definition of Done ✅

- [x] Kira bootstraps with a single `.env`
- [x] All integrations are OFF by default
- [x] Clear documentation in env.example
- [x] Settings validated at boot time

---

## 2. Single Writer Routing (Point 2)

### Implementation

**Enforced Pattern:** All vault entity mutations route through:

```
CLI/Plugins/Adapters → HostAPI → vault.py → md_io.py
```

### Files Refactored

Removed direct `open(..., 'w')` and `file.write_text()` for vault entities in:

1. **src/kira/cli/kira_task.py**
   - `update_task_metadata()` — Now uses `HostAPI.update_entity()`

2. **src/kira/cli/kira_context.py**
   - Context addition — Now uses `HostAPI.update_entity()`
   - Context removal — Now uses `HostAPI.update_entity()`

3. **src/kira/cli/kira_project.py**
   - `update_project_metadata()` — Now uses `HostAPI.update_entity()`

4. **src/kira/cli/kira_links.py**
   - `add_link_to_file()` — Now uses `HostAPI.update_entity()` with content parameter

5. **src/kira/cli/kira_note.py**
   - Tag management — Now uses `HostAPI.update_entity()`

### Vault.py Documentation

Updated `src/kira/storage/vault.py` with comprehensive single writer documentation:

```python
"""SINGLE WRITER PATTERN (Phase 0 Definition of Done):
====================================================
- ALL vault entity mutations MUST go through this layer
- NO direct `open(..., 'w')` allowed outside this module
- Route: CLI/Plugins/Adapters → HostAPI → vault.py → md_io.py

Enforcement verified by: grep -r "open(.*'w'" src/kira/{cli,plugins,adapters}
DoD: Zero offenders outside vault.py for entity writes.
"""
```

### Acceptable File Writes Outside Vault.py

The following file writes are ALLOWED as they don't write vault entities:

- **System files:** config, logs, quarantine, caches, aliases
- **Artifacts:** validation reports, backup metadata
- **Plugin storage:** Plugin-specific data (not vault entities)

### Definition of Done ✅

- [x] All CLI mutations route through `HostAPI.update_entity()`
- [x] No direct `open(..., 'w')` for vault entities outside vault.py
- [x] Verification command shows zero offenders:
  ```bash
  grep -r "open(.*'w'" src/kira/cli/*.py | grep -E "open\([^)]*[,\s]['\"']w['\"']"
  # Result: No direct writes found in CLI files
  ```

---

## Verification

### Runtime Flags Test

```bash
# Create minimal .env
echo "KIRA_VAULT_PATH=vault" > .env
echo "KIRA_MODE=alpha" >> .env

# Verify settings load correctly
python -c "
from src.kira.config.settings import load_settings
s = load_settings()
assert s.mode == 'alpha'
assert s.enable_gcal == False
assert s.enable_telegram == False
assert s.enable_plugins == False
print('✅ Phase 0 flags verified')
"
```

### Single Writer Test

```bash
# Verify no direct writes in CLI files
grep -r "open(" src/kira/cli/*.py | grep -E "open\([^)]*[,\s]['\"']w['\"']"
# Expected: No matches (exit code 1)

# Verify HostAPI is used
grep -r "host_api.update_entity" src/kira/cli/*.py
# Expected: Multiple matches in refactored files
```

---

## Migration Notes

### For Existing Code

If you have custom CLI commands or scripts that write to vault:

**Before (Phase 0 violation):**
```python
with open(task_path, "w") as f:
    f.write(new_content)
```

**After (Phase 0 compliant):**
```python
from kira.core.host import create_host_api
from kira.core.md_io import read_markdown

doc = read_markdown(task_path)
entity_id = doc.get_metadata("id")

host_api = create_host_api(vault_path)
host_api.update_entity(entity_id, {"status": "done"})
```

---

## Benefits

1. **Consistency:** All writes go through validation and atomic write protocol
2. **Safety:** No partial writes, no corruption from concurrent access
3. **Observability:** All mutations logged and traced through HostAPI
4. **Testability:** Single point to mock for testing
5. **Idempotency:** Built-in deduplication through HostAPI

---

## Next Steps (Phase 1)

With Phase 0 complete, the foundation is ready for:
- Canonical YAML schema enforcement
- UTC time discipline
- Task FSM with guards
- Domain validation at write boundary

---

## Checklist

### Phase 0, Point 1: Runtime Flags
- [x] `KIRA_MODE` environment variable
- [x] `KIRA_ENABLE_GCAL` flag (default: false)
- [x] `KIRA_ENABLE_TELEGRAM` flag (default: false)
- [x] `KIRA_ENABLE_PLUGINS` flag (default: false)
- [x] `KIRA_VAULT_PATH` required setting
- [x] `KIRA_DEFAULT_TZ` timezone setting
- [x] Updated config/env.example
- [x] Kira bootstraps with single .env

### Phase 0, Point 2: Single Writer
- [x] All CLI mutations through HostAPI
- [x] Refactored kira_task.py
- [x] Refactored kira_context.py
- [x] Refactored kira_project.py
- [x] Refactored kira_links.py
- [x] Refactored kira_note.py
- [x] Zero direct writes to vault entities
- [x] Comprehensive vault.py documentation
- [x] Verification grep shows no offenders

---

**Phase 0 Status:** ✅ COMPLETE — Ready for Phase 1

