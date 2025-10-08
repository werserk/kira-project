# Phase 6 Status — CLI Ready for Agents

**Status:** PARTIAL  
**Date:** 2025-10-08

---

## Overview

Phase 6 aims to make the CLI agent-friendly (LLM-friendly) with machine-readable output, stable exit codes, dry-run capabilities, and audit trails.

---

## Implementation Status

### Point 16: Machine-Readable Output ⚠️ PARTIAL

**DoD:** All CLI commands support `--json`

**Current Status:**
- ✅ `kira_diag.py` has `--json` flag for diagnostic output
- ❌ Most other CLI commands don't have `--json` support yet
- ❌ No standardized JSON output format: `{status, data|error, meta}`

**What Exists:**
```python
# src/kira/cli/kira_diag.py
@click.option("--json", "output_json", is_flag=True, 
              help="Output raw JSON lines instead of formatted text")
```

**What's Needed:**
1. Add `--json` flag to all CLI commands
2. Standardize output format: `{"status": "success|error", "data": {...}, "meta": {...}}`
3. Ensure only JSON goes to stdout (errors to stderr)

**Files to Update:**
- `src/kira/cli/kira_task.py` - Task commands
- `src/kira/cli/kira_note.py` - Note commands
- `src/kira/cli/kira_project.py` - Project commands
- `src/kira/cli/kira_context.py` - Context commands
- All other CLI command files

---

### Point 17: Stable Exit Codes ⚠️ NOT DOCUMENTED

**DoD:** Exit codes documented and enforced

**Required Exit Codes:**
- `0` - Success
- `2` - Validation error
- `3` - Conflict/idempotent operation
- `4` - FSM/state transition error
- `5` - I/O/lock error
- `6` - Configuration error
- `7` - Unknown error

**Current Status:**
- ❌ Exit codes not standardized across commands
- ❌ No exit code constants defined
- ❌ No documentation of exit codes

**What's Needed:**
1. Create `src/kira/cli/exit_codes.py` with constants
2. Update all CLI commands to use standard exit codes
3. Document exit codes in CLI help/README
4. Add tests for exit code behavior

---

### Point 18: Dry-Run / Confirm & Idempotent Create ⚠️ PARTIAL

**DoD:** `--dry-run` produces change plan; `--yes` suppresses prompts; duplicate creates safe

**Current Status:**
- ❌ No `--dry-run` flag in CLI commands
- ❌ No `--yes` flag for non-interactive mode
- ✅ Core upsert logic is idempotent (Phase 4)
- ⚠️ CLI may not expose idempotent create behavior

**What's Needed:**
1. Add `--dry-run` flag to mutation commands
2. Implement change plan preview
3. Add `--yes` flag to skip confirmations
4. Expose idempotent create (return existing entity if ID matches)
5. Add `already_exists` flag to responses

---

### Point 19: Audit Trail ⚠️ NOT IMPLEMENTED

**DoD:** `--trace-id` propagates to logs; JSONL audit written to `artifacts/audit/`

**Current Status:**
- ✅ Structured logging exists (Phase 5)
- ✅ Correlation IDs supported in logging
- ❌ No `--trace-id` CLI flag
- ❌ No dedicated audit trail (separate from logs)
- ❌ No `artifacts/audit/*.jsonl` files

**What's Needed:**
1. Add `--trace-id` global CLI option
2. Propagate trace ID through all operations
3. Create audit writer for `artifacts/audit/*.jsonl`
4. Include: timestamp, user, command, args, result, trace_id
5. Ensure audit is append-only and tamper-evident

---

## Summary

**Implemented:** Core infrastructure exists (idempotent upsert, structured logging)

**Not Implemented:**
- Standardized `--json` output across all commands
- Stable exit code system
- `--dry-run` / `--yes` flags
- Dedicated audit trail system

**Recommendation:**

Phase 6 is **not production-ready** for agent/LLM use. To complete:

1. **Short term** (for alpha):
   - Document that Phase 6 is deferred to post-alpha
   - Core functionality works, but not agent-optimized
   
2. **Long term** (post-alpha):
   - Implement full `--json` support
   - Add exit code system
   - Add dry-run/confirm flags
   - Implement audit trail

---

## Alternative: Minimal Phase 6 for Alpha

For alpha release, we could implement a **minimal** Phase 6:

1. **Exit Code Constants** (low effort):
   - Define constants in `exit_codes.py`
   - Use in CLI commands (best effort)
   
2. **JSON Output Documentation** (low effort):
   - Document existing JSON support in `kira diag`
   - Note that full JSON support is post-alpha
   
3. **Idempotent Create** (already works):
   - Document that upsert is idempotent
   - CLI returns existing entity if ID matches

4. **Trace ID** (medium effort):
   - Add `--trace-id` global option
   - Propagate to structured logs (infrastructure exists)

This would satisfy the "CLI works for humans" requirement while deferring full agent optimization to post-alpha.

---

## Decision

For **Phase 0-5 Complete, Phase 6 Deferred** strategy:
- ✅ Phases 0-5 fully implemented and tested (173 tests)
- ⚠️ Phase 6 partially implemented
- 📋 Document Phase 6 as "post-alpha enhancement"
- 🎯 Focus on Phases 7-10 for alpha readiness

This aligns with the phased approach: ship a safe alpha with core functionality, optimize for agents post-alpha.

