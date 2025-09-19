---
type: decision
id: ADR-007
title: YAML Schemas & Folder-Contracts as the single source of truth
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-002, ADR-006, ADR-008, ADR-015, ADR-016]
drivers: [unambiguity, deduplication, predictability, validation, developer experience]
---

## Context

Without formalized entity schemas and folder contracts, notes drift, links break, and tools cannot reliably operate. We need a single, authoritative description of entity structure and placement, consumable by both humans and machines.

## Decision

Adopt a dual-source model inside the Vault that together forms the single source of truth:

- Schemas: `.kira/schemas/*.yaml|*.json` define entity frontmatter and content constraints (JSON Schema-compatible).
- Folder-Contracts: README files at folder roots describe allowed entity kinds, naming, and layout constraints.

Validation runs in CI and within the Host API (`ctx.vault.write` in ADR-006). Schemas and contracts must be versioned and documented.

## Alternatives

- Free-form notes with conventions only — ambiguous, tool-hostile. Rejected.
- Centralized, code-only schemas outside the Vault — reduces portability/editability by users. Rejected.

## Implementation/Migration

1) Schema format and location
   - Store schemas under `.kira/schemas/` (YAML or JSON). Use JSON Schema Draft-07 subset consistent with SDK validators.
   - Provide examples and descriptions. Include `$id` and version fields for evolution.

2) Folder-Contracts
   - Each curated folder (e.g., `projects/`, `inbox/`, `archive/`) contains a README describing allowed kinds, required filename patterns, and subfolder rules.
   - Contracts can include simple selectors (by kind/tags) and path constraints.

3) Validation
   - CI job validates Vault against schemas and folder contracts using `core/schemas.py` and Host API hooks.
   - Report violations to an index such as `@Indexes/validation.md` with file paths and JSON Pointer error locations.

4) Templates and tooling
   - Auto-generate frontmatter templates from schemas preserving key order; expose CLI `kira vault new --kind <k>` to create valid stubs.
   - Add quick-fix suggestions for common violations.

5) Evolution
   - Version schemas; support additive changes without breaking existing content. Breaking changes require migration scripts and deprecation windows.

## Risks

- Migration noise — start with warnings for optional fields and gradually enforce.
- Divergence between schemas and contracts — mitigate via review and automated cross-checks.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Validation coverage:
  - ≥ 99% of Vault files validate successfully; remaining violations are tracked with owners and due dates.

- CI checks:
  - CI validates Vault content against `.kira/schemas` and folder contracts; failures show file path and JSON Pointer.

- Host enforcement:
  - `ctx.vault` rejects writes that break schemas or contracts with actionable errors and logs (ADR-006, ADR-015).

- Templates:
  - CLI can generate valid frontmatter templates for at least two kinds; generated files pass validation out-of-the-box.

- Documentation:
  - Folder READMEs exist and describe allowed kinds, naming, and layout; a canonical example is present.
