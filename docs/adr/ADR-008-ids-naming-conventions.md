---
type: decision
id: ADR-008
title: Stable identifiers and naming rules
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-006, ADR-007, ADR-015, ADR-016]
drivers: [idempotency, addressability, deduplication, predictability, UX]
---

## Context

Inconsistent naming breaks links and breeds duplicates. We need stable, human-meaningful identifiers with deterministic filenames and paths to keep Vault content consistent and tool-friendly.

## Decision

Adopt a stable ID format and deterministic file naming:

- ID format (required in frontmatter): `<kind>-YYYYMMDD-HHmm-<slug>`
  - `kind`: lowercase kebab-case entity kind (e.g., `note`, `task`, `meeting`).
  - Timestamp: local time in `Europe/Brussels` unless otherwise configured; 24h clock.
  - `slug`: kebab-case from title; normalized ASCII, trimmed, no stop words where feasible.

- Filename mapping: `<id>.md` (one entity per file). Paths use `kebab-case` directories; avoid spaces.

- Reserved characters: only `[a-z0-9-]` in IDs and slugs. Length ≤ 100 chars for filename safety.

- Backward compatibility: legacy IDs can be preserved and recorded in an alias list for link migration.

## Alternatives

- Pure UUIDs — opaque and worse for UX and search. Rejected.
- Title-only filenames — unstable across edits, break links. Rejected.

## Implementation/Migration

1) ID utilities `core/ids.py`
   - `generate_id(kind, title, when=now_tz)` → str
   - `slugify(title)` → str with safe normalization.
   - `validate_id(id_str)` → bool + error.

2) Host API integration (ADR-006)
   - On create, if `id` missing, generate; if present, validate and ensure global uniqueness.

3) Migration tooling
   - `scripts/rename_move.py`: rename files to `<id>.md`, update wikilinks/backlinks; write an alias map for redirects.

4) Time zone policy
   - Default `Europe/Brussels` for timestamps; configurable via `kira.yaml`.

5) Folder rules
   - Paths are kebab-case; ensure uniqueness within folders; collisions are prevented at Host API level.

## Risks

- Legacy links — mitigated by auto-rel linking and alias tracking.
- Locale variance — fixed zone + strict formatting.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Uniqueness:
  - No ID collisions across the Vault; attempts to create duplicates fail with clear errors.

- Determinism:
  - Given the same `kind`, `title`, and minute, `generate_id` returns the same ID; changing title changes only the slug part.

- Filesystem mapping:
  - All entities saved as `<id>.md`; migration tool updates existing files and fixes wikilinks/backlinks.

- Searchability and UX:
  - Search by `id` returns the entity in < 1s under nominal index size.

- Backward links:
  - No orphaned links after migration; alias map resolves old references where applicable.
