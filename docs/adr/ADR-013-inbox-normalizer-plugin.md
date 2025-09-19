---
type: decision
id: ADR-013
title: Inbox normalizer plugin (free-text → typed entities)
date: 2025-09-19
status: accepted
owners: [kira-plugins]
related: [ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007]
drivers: [reduce manual work, single entry point, consistency]
---

## Context

We need to convert raw messages/notes into typed Vault entities via a consistent pipeline and plugin, minimizing manual work while preserving accuracy and traceability.

## Decision

Adopt an Inbox Normalizer plugin that:

- Classifies inputs and extracts metadata to build entities such as `task | event | email_draft | meeting | research` based on schemas (ADR-007).
- For low-confidence extractions, queues `clarifications` and requests inline confirmations via Telegram (ADR-011).

## Alternatives

- Manual-only input — low efficiency and poor consistency. Rejected.

## Implementation/Migration

1) Schema-driven normalization
   - Use `.kira/schemas` to generate frontmatter templates; fill required fields and defaults.

2) IDs and links
   - Assign `id` (ADR-008) when creating entities; maintain relations (e.g., `for_project`, backlinks via Host API in ADR-006).

3) Event-driven processing
   - Subscribe to `message.received` and `file.dropped`; publish `inbox.normalized` upon success (ADR-005).

4) Clarification queue
   - Store uncertain cases with suggested fields; Telegram inline buttons confirm/amend.

5) Sandbox and permissions
   - All Vault writes go through `ctx.vault` (ADR-006); plugin runs in subprocess sandbox with minimal permissions (ADR-004).

## Risks

- False positives — mitigate with confirmations and iterative improvement.
- Overfitting rules — prefer small, composable extractors with tests.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Accuracy:
  - ≥90% precision on a sampled set of normalizations; the share of clarifications declines over time.

- Events:
  - `message.received` and `file.dropped` produce `inbox.normalized` on success; failures are logged with structured context.

- Vault writes:
  - Entities are created via Host API, have valid IDs, and validate against schemas.

- Tests:
  - Unit tests cover text normalization, metadata extraction, file processing, and command paths; integration test verifies bus events.
