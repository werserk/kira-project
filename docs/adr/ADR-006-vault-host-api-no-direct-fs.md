---
type: decision
id: ADR-006
title: Vault Host API; forbid direct FS writes by plugins
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-002, ADR-003, ADR-004, ADR-007, ADR-015, ADR-016]
drivers: [data integrity, folder contracts, validation, auditability, consistency]
---

## Context

Vault entities must be created/updated consistently and validated. Direct file system writes from plugins lead to broken links, duplicate IDs, and schema drift. We need a single Host API responsible for all mutations to the Vault with validation, ID assignment, link maintenance, and auditable logs.

## Decision

Adopt a Vault Host API as the sole write path. Plugins must not write directly to the Vault file system. All reads/writes go through `core/host.py` exposed to plugins via `ctx.vault` in the SDK.

- Write pipeline (Host API):
  - Validate payload against per-entity JSON Schemas in Vault `.kira/schemas` (ADR-007).
  - Enforce folder contracts (location, naming conventions, required frontmatter fields).
  - Generate stable unique IDs (ADR-008) if missing; prevent collisions and duplicates (ADR-016).
  - Persist Markdown with frontmatter via `core/md_io.py`.
  - Maintain link graph and backlinks via `core/links.py`.
  - Emit `entity.created|updated|deleted` events and structured JSONL logs (ADR-015).

- Read pipeline:
  - Resolve by ID or path, parse frontmatter and body, validate on-demand or opportunistically.

- Permissions and sandbox:
  - Plugins are forbidden from writing into the Vault via direct FS APIs. Sandbox policy (ADR-004) denies `fs.write` to Vault roots; only the Host API may mutate the Vault.
  - Optional per-plugin temp/work directories may be writable for transient files; they are not part of the Vault and are cleaned up.

## Alternatives

- Allow direct FS writes by plugins — fast but leads to duplicates, broken links, and bypasses validation. Rejected.
- Centralize only validation but allow writes — still race-prone and bypassable. Rejected.

## Implementation/Migration

1) Host API surface in `core/host.py`
   - `create_entity(kind, data) -> Entity`
   - `update_entity(entity_id, patch) -> Entity`
   - `upsert_entity(selector, data) -> Entity`
   - `delete_entity(entity_id) -> None`
   - `read_entity(entity_id|path) -> Entity`
   - `list_entities(kind, filters) -> Iterator[Entity]`

2) Validation and schemas in `core/schemas.py`
   - Load and cache `.kira/schemas/*.json`; validate before write and optionally on read.
   - Return structured errors with JSON Pointer paths for UX and logs.

3) Markdown IO in `core/md_io.py`
   - Read/write Markdown with YAML frontmatter; preserve formatting; atomic writes (temp file + rename).

4) Links and graph in `core/links.py`
   - Maintain forward/backlinks and consistency guards (ADR-016). Update graph on writes/moves/deletes.

5) SDK and sandbox integration
   - Expose `ctx.vault` facade in `kira.plugin_sdk.context` backed by Host API RPC; deny direct FS mutations in sandbox policy.

6) Migration
   - Identify any existing direct write paths in built-in plugins and refactor to use Host API.

## Risks

- Added latency from validation — mitigate with schema caching and a fast frontmatter parser; batch writes when possible.
- Lock contention on files — use atomic writes and minimal lock windows.
- Partial failures — ensure idempotent upserts and transactional sequences (validate → write → link update → events/logs).

## Metrics/DoD

Acceptance criteria (Definition of Done):

- No direct FS writes from plugins into Vault:
  - CI test scans plugin code to ensure no `open(...,'w')` or equivalent writes to Vault paths; sandbox policy denies such writes at runtime.

- Validation and contracts:
  - Writing invalid entities returns structured errors with field paths; valid entities persist successfully.
  - `.kira/schemas` are loaded and cached; a schema removal/addition is reflected after cache invalidation.

- IDs and deduplication:
  - IDs are generated when absent and are globally unique; duplicate prevention test passes (ADR-016).

- Link graph:
  - Creating or updating an entity updates backlinks; moving or deleting an entity updates/removes links accordingly.

- Events and logging:
  - `entity.created|updated|deleted` events are emitted; JSONL logs include correlation IDs, entity ID, path, and outcome (ADR-015).

- Performance:
  - Atomic writes; p95 write latency within acceptable bounds under nominal load.

Documentation:
  - `docs/` includes examples of using `ctx.vault` for create/update/delete.
