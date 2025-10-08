---
type: decision
id: ADR-009
title: Pipelines as thin orchestration (adapters↔plugins)
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-002, ADR-004, ADR-005, ADR-015]
drivers: [simplicity, observability, reusability, testability]
---

## Context

We need explicit glue between event sources (adapters) and plugin actions, without embedding business logic in orchestration. Pipelines should be small, predictable, and easy to test.

## Decision

Adopt thin pipelines that only handle routing, minimal mapping, retries, and telemetry. All business logic remains in plugins (via SDK events/commands).

- Standard pipelines:
  - `inbox_pipeline` — normalizes incoming items and forwards to the inbox plugin(s).
  - `sync_pipeline` — coordinates periodic pulls/pushes and publishes `sync.tick` events.
  - `rollup_pipeline` — triggers rollup generation on schedules or on demand.

## Alternatives

- “God” pipelines carrying business logic — hard to test/extend; violates plugin boundaries. Rejected.
- Direct adapter→plugin calls without pipelines — reduces visibility and control. Rejected.

## Implementation/Migration

1) Structure
   - Each pipeline is a class with a `run()` entrypoint and small helpers; no shared mutable state.
   - Use the event bus (ADR-005) to publish/subscribe rather than direct calls.

2) Error handling and retries
   - Retries are applied at pipeline boundaries with backoff and jitter; failures are logged with correlation IDs.

3) Telemetry
   - Emit JSONL logs with `trace_id` for the entire path from adapter input to plugin handling (ADR-015).

4) Config and CLI
   - Configuration is minimal and injected via constructor; expose `kira pipelines <name>` commands in CLI.

5) Tests
   - Provide unit tests for pipeline control flow and integration tests that assert end-to-end event propagation.

## Risks

- Explosion of pipelines — maintain a catalog and naming rules; merge overlapping ones.
- Hidden logic creep — review guardrails to keep pipelines thin.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Thinness:
  - Pipelines contain no domain logic; checks in code review and lints ensure only routing/mapping/retry code exists.

- Observability:
  - Any end-to-end scenario is traceable with a single `trace_id` in JSONL logs across adapter → pipeline → plugin.

- Reliability:
  - Retry behavior verified in tests; failures are logged with structured context and capped retries.

- Test coverage:
  - Unit tests cover control flow; integration tests for inbox/sync/rollup paths are green and assert events are delivered.
