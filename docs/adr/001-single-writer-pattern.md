# ADR-001: Single Writer Pattern via Host API

## Status

**Accepted** (Phase 0, Point 1)

## Context

Kira manages a vault of markdown files with YAML front-matter. Multiple components (CLI, adapters, plugins) need to modify these files. Without coordination, this leads to:

- **Race conditions**: Concurrent writes corrupting files
- **Lost updates**: Read-modify-write cycles losing changes
- **Inconsistent state**: Different components with different validation rules
- **Difficult debugging**: No central point to trace mutations

Traditional approaches (file locks only, optimistic locking) are insufficient for a file-based vault with multiple writers.

## Decision

We implement the **Single Writer Pattern** via `HostAPI`:

### Architecture

```
┌─────────────┐
│     CLI     │
└─────┬───────┘
      │
┌─────▼───────┐     ┌────────────┐
│   Adapter   ├────►│  HostAPI   │
└─────────────┘     │ (Gateway)  │
                    └─────┬──────┘
┌─────────────┐           │
│   Plugin    ├───────────┘
└─────────────┘           │
                    ┌─────▼──────┐
                    │   Vault    │
                    │ (Storage)  │
                    └────────────┘
```

### Rules

1. **All writes go through HostAPI**: No direct file writes outside `vault.py`
2. **HostAPI coordinates**: Validation, FSM guards, event emission, atomicity
3. **Vault layer**: Provides low-level atomic writes + per-entity file locks
4. **No bypasses**: Even CLI and admin tools use HostAPI

### Implementation

```python
# ✓ CORRECT: Via HostAPI
host_api.create_entity("task", data)
host_api.update_entity(uid, changes)
host_api.delete_entity(uid)

# ✗ WRONG: Direct file writes
with open(file_path, 'w') as f:
    f.write(content)
```

## Consequences

### Positive

- **Consistency**: Single point of validation and business logic
- **Traceability**: All mutations logged and observable
- **Safety**: Atomic writes + file locks prevent corruption
- **Testability**: Mock HostAPI for unit tests
- **Auditability**: Easy to add audit log at gateway

### Negative

- **Performance**: Extra indirection (minimal in practice)
- **Migration cost**: Existing code must be refactored
- **Learning curve**: Developers must understand the pattern

### Risks Mitigated

- **Data corruption**: Eliminated by atomic writes + locks
- **Lost updates**: Prevented by serialized access per entity
- **Validation bypass**: Impossible without modifying HostAPI

## Verification

### DoD Check

```bash
# Verify no direct writes outside vault.py
grep -r "open.*'w'" src/ --exclude-dir=storage
# Should return 0 results
```

### Tests

- `tests/unit/test_vault.py`: Storage layer tests
- `tests/unit/test_host_api.py`: Gateway tests
- `tests/integration/`: End-to-end flows

## References

- Implementation: `src/kira/core/host.py`, `src/kira/storage/vault.py`
- Pattern: Martin Fowler's Gateway pattern
- Related: ADR-002 (YAML Schema), ADR-003 (Idempotency)
