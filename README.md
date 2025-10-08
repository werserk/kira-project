# Kira - Personal Knowledge Management System

**Production-ready PKM system with robust business-logic pipeline**

[![Tests](https://img.shields.io/badge/tests-744%2F821%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

## Quick Start (< 30 minutes)

### Prerequisites

- Python 3.12+
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/kira-project.git
cd kira-project

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt  # If exists, or:
pip install -e .

# Run tests to verify
pytest tests/unit/ -v
```

### Configuration

Create `.env` file:

```bash
# Vault location
KIRA_VAULT_PATH=~/kira-vault

# Timezone (default: Europe/Brussels)
KIRA_TIMEZONE=America/New_York

# Logging
KIRA_LOG_LEVEL=INFO
KIRA_LOG_FORMAT=json

# Optional: Google Calendar sync
GCAL_CLIENT_ID=your-client-id
GCAL_CLIENT_SECRET=your-secret
```

### First Run

```bash
# Initialize vault
python -m kira.cli init

# Create your first task
python -m kira.cli task create "Setup Kira" --tags setup

# List tasks
python -m kira.cli task list

# Run migration (if you have existing vault)
python -m kira.migration.cli ~/existing-vault --dry-run
```

**Done!** You now have a working Kira installation. Read on for architecture details.

---

## Architecture Overview

Kira is built on **8 completed phases** implementing a robust business-logic pipeline:

```
Ingress (Telegram/GCal/CLI)
    ↓ Normalize & Validate
Event Bus (at-least-once)
    ↓ Idempotent Processing
Business Logic (FSM + Validation)
    ↓ Single Writer Pattern
Vault (Atomic Writes + Locks)
    ↓ Two-Way Sync
External Systems (GCal)
```

### Key Principles

1. **Single Writer**: All mutations via `HostAPI` (ADR-001)
2. **UTC Core**: All timestamps stored in UTC (ADR-005)
3. **Idempotent**: Events processed exactly once (ADR-003)
4. **Atomic**: Crash-safe file writes (Phase 3)
5. **Validated**: Business rules enforced before write (Phase 1)
6. **Observable**: Structured logging for all operations (Phase 5)

### Data Model

Entities are stored as Markdown files with YAML front-matter:

```markdown
---
id: task-20251008-1430-fix-auth-bug
title: Fix authentication bug
created: 2025-10-08T14:30:00+00:00
updated: 2025-10-08T15:45:00+00:00
status: doing
tags:
  - bug
  - urgent
assignee: alice
---
# Description

The authentication flow has a race condition...
```

**Entity Types:**
- **Task**: Workflow items with FSM (todo → doing → done)
- **Note**: Knowledge capture
- **Event**: Calendar items (syncs with GCal)

See [ADR-002](docs/adr/002-yaml-frontmatter-schema.md) for complete schema.

---

## Core Concepts

### 1. Single Writer Pattern (ADR-001)

**All writes go through HostAPI.**

```python
# ✓ CORRECT
from kira.core.host import create_host_api

host_api = create_host_api(vault_path)
host_api.create_entity("task", {"title": "Buy milk", "status": "todo", "tags": []})
host_api.update_entity(uid, {"status": "done"})

# ✗ WRONG: Direct file writes
with open(file_path, 'w') as f:
    f.write(content)
```

**Why?** Ensures:
- Validation before write
- Atomic operations
- Event emission
- Audit trail

### 2. Event Idempotency (ADR-003)

Events have deterministic IDs for deduplication:

```python
from kira.core.idempotency import generate_event_id, EventDedupeStore

# Generate stable ID
event_id = generate_event_id(
    source="telegram",
    external_id="msg-12345",
    payload={"text": "Buy milk"}
)

# Check + mark seen
dedupe_store = EventDedupeStore(db_path)
if not dedupe_store.is_duplicate(event_id):
    dedupe_store.mark_seen(event_id)
    process_event(payload)
```

**Why?** Handles:
- Network retries
- Webhook replays
- At-least-once delivery

### 3. UTC Time Discipline (ADR-005)

**All timestamps in UTC. Always.**

```python
from kira.core.time import get_current_utc, format_utc_iso8601

# Store in UTC
now_utc = get_current_utc()
timestamp = format_utc_iso8601(now_utc)
# "2025-10-08T14:30:00+00:00"

# Display in user timezone
from kira.core.time import localize_to_timezone
local_dt = localize_to_timezone(now_utc, "America/New_York")
```

**Why?** Avoids:
- DST bugs (23/25-hour days)
- Comparison errors
- Mixed timezone chaos

### 4. FSM Guards (Phase 1)

Tasks follow state machine with guards:

```python
# todo → doing: requires assignee OR start_ts
host_api.update_entity(uid, {
    "status": "doing",
    "assignee": "alice"  # Guard satisfied
})

# doing → done: sets done_ts automatically
host_api.update_entity(uid, {"status": "done"})
# done_ts added by FSM

# done → doing: requires reopen_reason
host_api.update_entity(uid, {
    "status": "doing",
    "reopen_reason": "Found regression"  # Guard satisfied
})
```

**Why?** Enforces business rules at system level.

---

## Development Guide

### Project Structure

```
kira-project/
├── src/kira/
│   ├── core/           # Core business logic
│   │   ├── host.py     # HostAPI (gateway)
│   │   ├── validation.py  # Domain validation
│   │   ├── fsm.py      # Task state machine
│   │   ├── idempotency.py  # Event dedup
│   │   └── time.py     # UTC utilities
│   ├── storage/
│   │   └── vault.py    # File storage layer
│   ├── sync/
│   │   ├── contract.py # Sync metadata
│   │   └── ledger.py   # Echo prevention
│   ├── rollups/
│   │   └── time_windows.py  # DST-aware aggregation
│   ├── migration/
│   │   └── migrator.py # Vault migration
│   └── plugins/
│       └── sandbox.py  # Plugin isolation
├── tests/
│   ├── unit/           # Unit tests (700+ tests)
│   └── integration/    # Integration tests (24 tests)
├── docs/
│   └── adr/            # Architecture decisions
└── .github/
    └── workflows/      # CI/CD
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_idempotency.py -v

# With coverage
pytest --cov=src/kira tests/
```

### Code Style

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
ruff check src/
```

### Adding a New Feature

1. **Read relevant ADRs** (see [docs/adr/](docs/adr/))
2. **Write tests first** (TDD)
3. **Implement through HostAPI** (Single Writer pattern)
4. **Validate inputs** (use `validation.py`)
5. **Log operations** (structured logging)
6. **Update documentation**

---

## Architecture Decision Records (ADRs)

**Must-read for all developers** (~20 minutes total):

| ADR | Title | Why Important |
|-----|-------|---------------|
| [001](docs/adr/001-single-writer-pattern.md) | Single Writer Pattern | Foundation of data consistency |
| [002](docs/adr/002-yaml-frontmatter-schema.md) | YAML Schema | Data structure & serialization |
| [003](docs/adr/003-event-idempotency.md) | Event Idempotency | Reliable event processing |
| [004](docs/adr/004-event-envelope.md) | Event Envelope | Inter-system communication |
| [005](docs/adr/005-timezone-policy.md) | UTC Timezone Policy | Time handling discipline |
| [006](docs/adr/006-gcal-sync-policy.md) | GCal Sync Policy | Two-way sync without loops |
| [007](docs/adr/007-plugin-sandbox.md) | Plugin Sandbox | Security model |

**Reading order:** 001 → 002 → 005 → 003 → 004 → 006 → 007

---

## Phase Status

| Phase | Description | Status | Tests |
|-------|-------------|--------|-------|
| 0 | Foundations & Single Writer | ✅ Complete | 48/48 |
| 1 | Business Invariants (FSM) | ✅ Complete | 36/36 |
| 2 | Idempotency & Event Flow | ✅ Complete | 95/95 |
| 3 | Safe Storage (Atomicity) | ✅ Complete | 34/34 |
| 4 | Two-Way GCal Sync | ✅ Complete | 43/43 |
| 5 | Security & Observability | ✅ Complete | 64/64 |
| 6 | Integration & Stress Tests | ✅ Complete | 24/24 |
| 7 | Rollups & Time Windows | ✅ Complete | 30/30 |
| 8 | Migration | ✅ Complete | 22/22 |
| **Total** | | **91% passing** | **744/821** |

---

## Common Tasks

### Migrate Existing Vault

```bash
# Dry run (preview changes)
python -m kira.migration.cli ~/my-vault --dry-run --verbose

# Actual migration
python -m kira.migration.cli ~/my-vault

# Verify post-migration
pytest tests/unit/test_migration.py::test_dod_round_trip_after_migration
```

### Query Time Windows

```python
from datetime import datetime
from kira.rollups.time_windows import compute_day_boundaries_utc

# Get UTC boundaries for local day (handles DST)
start_utc, end_utc = compute_day_boundaries_utc(
    datetime(2025, 3, 9),  # DST transition day
    "America/New_York"
)
# Returns: 23-hour day (spring forward)
```

### Run Plugin in Sandbox

```python
from kira.plugins.sandbox import PluginSandbox

sandbox = PluginSandbox(plugin_dir, config)
result = sandbox.run(
    plugin_name="my-plugin",
    input_data={"task_id": "task-123"},
)
```

---

## Troubleshooting

### Issue: "ValidationError: Entity validation failed"

**Cause:** Entity doesn't meet schema requirements

**Fix:** Check required fields in [ADR-002](docs/adr/002-yaml-frontmatter-schema.md)

```python
# Task requires: id, title, created, updated, status, tags
host_api.create_entity("task", {
    "title": "My task",
    "status": "todo",
    "tags": [],  # Don't forget this!
})
```

### Issue: "FSM guard failed: todo → doing"

**Cause:** State transition missing required guard

**Fix:** Add `assignee` or `start_ts`

```python
# ✓ Valid
host_api.update_entity(uid, {
    "status": "doing",
    "assignee": "alice"
})
```

### Issue: Duplicate events processing

**Cause:** Not using idempotency store

**Fix:** Check dedup before processing

```python
event_id = generate_event_id(source, external_id, payload)
if dedupe_store.is_duplicate(event_id):
    return  # Skip duplicate
dedupe_store.mark_seen(event_id)
```

---

## Contributing

1. Read [ADRs](docs/adr/) to understand architecture
2. Create feature branch: `git checkout -b feature/my-feature`
3. Write tests first (TDD)
4. Implement feature (follow patterns in ADRs)
5. Run tests: `pytest`
6. Run linters: `black .`, `mypy .`, `ruff check .`
7. Submit PR with clear description

---

## Support

- **Documentation**: [docs/](docs/)
- **ADRs**: [docs/adr/](docs/adr/)
- **Issues**: GitHub Issues
- **Tests**: `pytest tests/ -v` for examples

---

## License

MIT License - see LICENSE file

---

**Built with love for personal knowledge management** 🚀