---
type: decision
id: ADR-015
title: Structured logs/telemetry for core/adapters/plugins/pipelines
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-004, ADR-005, ADR-009]
drivers: [explainability, debugging, reliability, operations]
---

## Context

We need end-to-end traceability and performance/error metrics across core, adapters, plugins, and pipelines.

## Decision

Adopt structured JSONL logs with trace propagation, per-component files, and a diagnostic CLI.

- Storage layout: `logs/{core,adapters,plugins,pipelines}/*.jsonl` with rotation/compression.
- Core fields: `timestamp`, `level`, `trace_id`, `span_id`, `component`, `message`, `latency_ms`, `outcome`, `refs[]`, `error{type,message,stack}`.
- Context fields: `plugin`, `adapter`, `pipeline`, `event`, `job_id`, `entity_id`, `chat_id` as applicable.
- CLI: `kira diag tail --component X` tails merged view with filters (trace_id, level, time window).

## Alternatives

- Free-form prints — unsearchable and uncorrelated. Rejected.
- Centralized APM first — overkill for MVP; can be added later with the same fields.

## Implementation/Migration

1) Logger
   - Provide a shared logger that writes JSONL; expose in `ctx.logger` in SDK.
   - Generate/propagate `trace_id` at event ingress; create `span_id` per operation.

2) Correlation
   - Bus and scheduler attach/propagate trace context (ADR-005). Sandbox forwards context via RPC (ADR-004).

3) Rotation and retention
   - Implement size/time-based rotation; compress old files; document retention policy.

4) CLI
   - Implement `kira diag tail` with filters; support `--trace-id`, `--level`, `--since`.

## Risks

- Log volume — mitigate with rotation/compression and configurable levels.
- PII — redact sensitive fields by default; allow opt-in verbose with safeguards.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Traceability:
  - Any end-to-end flow is reconstructible from logs using a single `trace_id`; spans show durations and outcomes.

- Diagnostics:
  - `kira diag tail` filters by component/trace/level and outputs structured lines.

- Operations:
  - Rotation/compression configured; log size within target budgets over a week of nominal usage.
