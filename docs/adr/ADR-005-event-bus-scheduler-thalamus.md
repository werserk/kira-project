---
type: decision
id: ADR-005
title: Event bus and scheduler as the system thalamus
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-002, ADR-004, ADR-009, ADR-015]
drivers: [low coupling, reactivity, predictability, observability]
---

## Context

We want adapters → pipelines → plugins to be loosely coupled and reactive. A central event bus and a scheduler act as the “thalamus” of the system: routing signals, orchestrating periodic/one-off work, and enabling testable, observable flows.

## Decision

Provide a lightweight in-process event bus with publish/subscribe APIs, filters, retries, and structured logging, and a scheduler supporting `cron`, `interval`, and `at` triggers with pipeline integration. Canonical events are standardized and documented.

- Event bus (`core/events.py`):
  - Topics use dot-separated names (e.g., `message.received`, `file.dropped`, `entity.created`, `task.due_soon`, `meeting.finished`, `sync.tick`).
  - API: `publish(event_name, payload, *, headers)`, `subscribe(event_name, handler, *, filter=None, once=False)`.
  - Delivery: synchronous by default for determinism, with an async queue variant for high-volume paths.
  - Reliability: in-memory queue with bounded size; retry policy for handler exceptions with backoff and jitter.
  - Observability: each delivery is logged as JSONL with correlation IDs and handler outcomes (ADR-015).

- Scheduler (`core/scheduler.py`):
  - Triggers: `interval(seconds)`, `at(iso_datetime)`, `cron(expr)`.
  - Jobs: identified by stable IDs; support idempotent scheduling and cancellation.
  - Integration: pipelines can register periodic sync ticks; plugins can request schedules via SDK (subject to permissions in ADR-004).
  - Fault handling: missed runs are optionally coalesced; long-running jobs receive cancellation tokens; timeouts enforced by host.

- Canonical events:
  - Define and document a small core set to avoid taxonomy drift. Extensions require ADR or registry updates.

## Alternatives

- Direct module-to-module calls — couples components tightly and complicates testing. Rejected.
- External MQ (e.g., Redis/Kafka) for MVP — operational overhead and premature complexity. May be considered later behind the same API.

## Implementation/Migration

1) Event bus API and semantics
   - Implement `publish/subscribe` with handler metadata (name, plugin, retry policy). Provide filter predicates.
   - Add sync and async delivery modes; default to sync, allow opt-in async per topic.

2) Scheduler primitives
   - Implement job store (in-memory for MVP), trigger parsing, and execution loop with backoff on failures.
   - Expose `schedule_interval`, `schedule_at`, `schedule_cron`, `cancel(job_id)` via SDK RPC (permission `scheduler.create/cancel`).

3) Observability and tracing
   - Add JSONL logs for publish, delivery, success/failure, scheduling, execution, cancellations with correlation IDs (ADR-015).

4) Canonical event registry
   - Define constants or a registry module enumerating canonical events with docstrings and payload schemas.

5) Backends
   - Design the bus/scheduler with pluggable backends to allow swapping to external MQ/cron later without API break.

## Risks

- Event loss under process crash — acceptable for MVP; mitigate with at-least-once retries and consider durable backends later.
- Handler latency causing backpressure — mitigate with async mode and bounded queues for hot topics.
- Cron parsing differences — standardize on a single parser and document supported features.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Latency and reliability:
  - Delivery latency p95 < 100 ms under nominal load; zero lost events in stress tests without process crashes.

- Retry semantics:
  - Failing handlers are retried according to policy with backoff and jitter; exhaustion is logged with context.

- Scheduler correctness:
  - Interval/at/cron jobs fire within acceptable drift (≤ 1s interval, ≤ 2s at, cron within minute granularity).
  - Jobs can be listed and cancelled deterministically; missed runs policy is honored.

- Observability:
  - JSONL logs include event names, job IDs, durations, outcomes, and correlation IDs consumable by ADR-015 pipeline.

- API stability:
  - Public bus and scheduler APIs are documented and covered by unit and integration tests.
