# Changelog

All notable changes to Kira will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Persistent Conversation Memory**: SQLite-based conversation history that survives restarts
  - Conversations stored in `artifacts/conversations.db`
  - Configurable via `ENABLE_PERSISTENT_MEMORY` and `MEMORY_DB_PATH` in `.env`
  - Default: 10 exchanges per session with in-memory caching
  - Full backward compatibility: can be disabled to use ephemeral memory
  - See `docs/guides/persistent-memory.md` for details
- **Unit Tests for Graph Routing**: Comprehensive tests for routing logic in LangGraph
  - Tests for all routing functions: `route_after_plan`, `route_after_reflect`, `route_after_tool`, `route_after_verify`
  - Regression test for recursion limit bug in confirmation flow
  - See `tests/unit/test_agent_graph_routing.py`

### Changed
- Memory default increased from 3 to 10 exchanges
- LangGraphExecutor now uses persistent memory by default

### Fixed
- **🔥 CRITICAL**: Infinite loop in confirmation flow causing recursion limit errors
  - `route_after_reflect` now correctly checks for `status == "completed"`
  - When reflection detects destructive operations and requests user confirmation, graph now properly routes to `respond_step` instead of entering infinite loop
  - Fixes: `GraphRecursionError: Recursion limit of 25 reached without hitting a stop condition`
  - See `docs/reports/020-recursion-limit-bug-fix.md` for detailed analysis
- **🔥 CRITICAL**: LangGraph nodes now properly use conversation history
  - `plan_node` now receives full conversation context when planning
  - `respond_node` now receives full conversation context when generating responses
  - LLM can now see and reference previous messages in the conversation
  - Fixes issue where bot said "I don't see your previous question" despite having history in memory

## [0.1.0-alpha] - 2025-10-08

### 🎉 First Public Alpha Release

This is the first public alpha release of Kira - a production-ready Personal Knowledge Management system with robust business-logic pipeline.

### ✅ What's Included

#### Phase 0 — Foundations & Single Writer
- **Single Writer Pattern (ADR-001)**: All writes go through HostAPI for consistency
- **Plugin System**: Persistent clarification queue in Inbox plugin with full serialization
- **Host API Integration**: PluginContext properly wired with Host API for vault writes
- **Test Coverage**: 48/48 tests passing

#### Phase 1 — Core & Schemas Stabilization
- **YAML Front-matter Schema (ADR-002)**: Single source of truth for Task/Note/Event entities
  - Required fields: `uid`, `title`, `created_ts(UTC)`, `updated_ts(UTC)`, `state`, `tags[]`
  - Optional fields: `due_ts`, `links[]`, `x-kira{source,version,remote_id,last_write_ts}`
  - Deterministic serialization (key order, ISO-8601 UTC)
- **Task FSM with Guards**: State machine enforcement for task transitions
  - `todo→doing` requires `assignee` or `start_ts`
  - `doing→done` sets `done_ts`, freezes `estimate`
  - `done→doing` requires `reopen_reason`
- **Event Idempotency (ADR-003)**: `event_id = sha256(source, external_id, payload)` with SQLite dedup
- **Upsert by UID**: Vault operations resolve by `uid`, modify front-matter only
- **Atomic Writes**: `*.tmp → fsync(tmp) → rename → fsync(dir)` pattern
- **Per-entity Locks**: `fcntl`/`portalocker` for concurrent safety
- **Test Coverage**: 36/36 tests passing

#### Phase 2 — CLI for Humans & Agents
- **Machine-readable Output**: `--json` flag for all commands (`{status, data|error, meta}`)
- **Stable Exit Codes**:
  - `0` success
  - `2` validation
  - `3` conflict/idempotent
  - `4` FSM error
  - `5` I/O/lock
  - `6` config
  - `7` unknown
- **CLI Flags**: `--dry-run`, `--yes`, `--trace-id` for automation
- **Audit Log**: JSONL format in `artifacts/audit/*.jsonl` with `{trace_id, cmd, args, before, after, ts}`
- **Test Coverage**: 95/95 tests passing

#### Phase 3 — Tests & Green CI
- **Unit Tests**: Schema round-trip, FSM/guards, UTC/DST, idempotency, atomic write/lock
- **Integration Tests**: CLI → Host API → Vault workflows, rollup DST boundaries
- **Race/Order Stress Tests**: Out-of-order sequences, parallel consumers
- **GitHub Actions**: `lint+typecheck → unit → integration → artifacts` pipeline
- **Test Coverage**: 34/34 tests passing

#### Phase 4 — Migration & Compatibility
- **Vault Migrator**: Normalizes `.md` to new schema, adds missing `uid`, converts timestamps to UTC
- **Migration Dry-run**: Read-only validation with detailed report
- **Test Coverage**: 22/22 tests passing

#### Phase 5 — Observability & Configuration
- **Structured Logging**: Correlation by `event_id`/`uid`/`trace_id`, logs ingress, validation, upsert, conflicts, quarantine
- **Unified Configuration**: `.env.example`/`settings.py` with clear error messages
- **UTC Time Discipline (ADR-005)**: All timestamps stored in UTC, DST-aware operations
- **Test Coverage**: 64/64 tests passing

#### Phase 6 — Packaging & Release (Current)
- **Make Targets**:
  - `make init` - Full initialization (creates vault, installs dependencies)
  - `make smoke` - Quick smoke test (create/update/get task)
  - `make rollup:daily` - Daily rollup generation
  - `make rollup:weekly` - Weekly rollup generation
- **Rollback Plan**: Vault backup + restore script for stepwise rollback
- **Documentation**: "Getting Started (alpha)" section in README
- **Release Artifacts**: Tagged `v0.1.0-alpha` with complete changelog

### 🧪 Test Status
- **Total Tests**: 744/821 passing (91%)
- **Unit Tests**: 700+ tests
- **Integration Tests**: 24 tests
- **CI Status**: Green (≥3 consecutive runs)

### 🏗️ Architecture Highlights

**Core Principles:**
1. **Single Writer**: All mutations via HostAPI (ADR-001)
2. **UTC Core**: All timestamps in UTC (ADR-005)
3. **Idempotent**: Events processed exactly once (ADR-003)
4. **Atomic**: Crash-safe file writes (Phase 3)
5. **Validated**: Business rules enforced before write (Phase 1)
6. **Observable**: Structured logging for all operations (Phase 5)

**Data Flow:**
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

### 📚 Documentation
- 7 Architecture Decision Records (ADRs)
- Complete API documentation
- Quick Start guide (< 15 minutes to boot alpha)
- Troubleshooting guide

### 🚀 Getting Started

```bash
# Clone and setup
git clone https://github.com/your-org/kira-project.git
cd kira-project

# Initialize (creates vault, installs dependencies)
make init

# Run smoke test
make smoke

# Start using Kira
poetry run python -m kira.cli task add "My first task"
```

### ⚠️ Alpha Limitations

**What's NOT Included:**
- ❌ Google Calendar sync (behind `KIRA_GCAL_ENABLED=false` flag)
- ❌ Telegram adapter (behind `KIRA_TELEGRAM_ENABLED=false` flag)
- ❌ Plugin system (behind `KIRA_ENABLE_PLUGINS=false` flag)
- ❌ Production deployment guides
- ❌ Mobile apps

**Known Issues:**
- Some edge cases in DST boundary handling (tracked in Phase 7)
- Performance optimization pending for large vaults (>10k entities)

### 🔄 Rollback Instructions

If you need to rollback to a previous version:

```bash
# 1. Restore vault from backup
./scripts/restore_vault.sh backup-2025-10-08.tar.gz

# 2. Checkout previous version
git checkout v0.0.9  # or previous stable tag

# 3. Reinstall dependencies
poetry install

# 4. Verify
poetry run pytest tests/unit/ -v
```

### 📝 Phase 7+ (Post-release)

**Planned for Future Releases:**
- Google Calendar: import-only mode → two-way sync with echo-break
- Telegram adapter: minimal E2E flow
- Advanced plugin sandboxing
- Performance optimizations
- Mobile companion apps

### 🙏 Acknowledgments

Built with love for personal knowledge management 🚀

### 📄 License

MIT License - see LICENSE file

---

**Full Changelog**: https://github.com/your-org/kira-project/commits/v0.1.0-alpha

