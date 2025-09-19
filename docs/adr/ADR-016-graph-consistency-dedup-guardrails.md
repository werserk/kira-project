---
type: decision
id: ADR-016
title: Graph consistency checks and deduplication guardrails
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-006, ADR-007, ADR-008, ADR-015]
drivers: [knowledge integrity, unambiguity, maintainability]
---

## Context

As the knowledge base grows, issues appear: orphaned nodes, cycles in `depends_on`, title-based duplicates, and broken wikilinks. We need automated checks and guardrails to keep the graph healthy.

## Decision

Adopt a graph validation toolset (`core/links.py` and `scripts/graph_report.py`) that finds orphans, cycles, duplicates (by `title+context` or fuzzy), and broken wikilinks, with nightly validation and a report in `@Indexes/graph_report.md`.

## Alternatives

- Manual review — does not scale. Rejected.

## Implementation/Migration

1) Graph model
   - Extract nodes (entities) and edges (wikilinks, `depends_on`, `for_*`) from Vault; build adjacency lists.

2) Checks
   - Orphans: nodes with zero in/out edges (excluding configured kinds/folders).
   - Cycles: detect cycles in `depends_on` DAG with DFS/Tarjan.
   - Duplicates: heuristic matching on normalized `title+kind+context`; optional fuzzy distance threshold.
   - Broken links: wikilinks or references pointing to missing IDs/paths.

3) Reporting
   - `kira validate` generates `@Indexes/graph_report.md` with sections per issue type and suggested fixes.

4) Auto-fix (optional)
   - Disabled by default. When enabled, propose PR-like sets: fix links, merge duplicates, or add redirects/aliases.

5) Tests
   - Integration test against a sample Vault; unit tests for each checker.

## Risks

- Aggressive auto-fixes — keep report-only by default; require explicit opt-in for write changes.
- False positives — tune thresholds and allow per-folder/kind ignores.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Consistency:
  - Zero cycles in `depends_on` and zero broken wikilinks after initial fix round.

- Orphans and duplicates:
  - Orphan count is reported with owners; duplicate trend declines week-over-week.

- Automation:
  - Nightly job produces `@Indexes/graph_report.md`; CI fails on newly introduced cycles or broken links.
