---
type: decision
id: ADR-012
title: Google Calendar adapter + calendar plugin for sync & timeboxing
date: 2025-09-19
status: accepted
owners: [kira-adapters, kira-plugins]
related: [ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-009]
drivers: [no missed meetings/deadlines, reliable sync, timeboxing]
---

## Context

We need reliable two-way synchronization between Vault entities and Google Calendar, and automatic timeboxing for tasks entering execution.

## Decision

Adopt a GCal adapter plus a calendar plugin:

- Source of truth (MVP): Google Calendar is authoritative for events; Vault mirrors. Tasks with `due` map to all-day events or timeboxed blocks based on `time_hint`.
- Commands: `calendar.pull|push`. Timeboxing triggers on task FSM transition `enter_doing` by publishing a scheduling event.

- Mapping rules:
  - Vault event ↔ GCal event 1:1. Fields: title, start/end, attendees (subset), description link to Vault entity.
  - Vault task with `due` → all-day GCal event on due date unless `time_hint` present, in which case schedule a block of that length.
  - IDs: store GCal `event.id` in Vault frontmatter for reconciliation.

## Alternatives

- Local calendar only — weaker ecosystem/integration. Deferred.
- Push-only or pull-only — brittle and one-sided. Rejected.

## Implementation/Migration

1) Adapter `adapters/gcal/adapter.py`
   - `pull(calendar_id, days)` fetches events; normalizes and publishes `event.received` (ADR-005).
   - `push(calendar_id, dry_run)` reads Vault changes and updates GCal.

2) Plugin `plugins/calendar`
   - Subscribes to sync events; maintains Vault↔GCal mapping and persists GCal IDs in frontmatter.
   - Listens for `task.enter_doing` to timebox via scheduler (ADR-005).

3) Reconciliation
   - Nightly reconcile compares Vault and GCal by IDs and timestamps; resolves conflicts with last-writer-wins plus audit logs.

4) Permissions and sandbox
   - Requires `net`, `secrets.read` for OAuth tokens; all network calls go through sandbox policy (ADR-004).

## Risks

- Drift between GCal and Vault — mitigate with frequent pulls, ID anchoring, and nightly reconcile.
- Rate limits — backoff and incremental syncing windows.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Sync correctness:
  - Nightly reconcile reports zero unresolved divergences; conflicts are logged and resolved deterministically.

- Latency:
  - Typical pull/push completes in < 2s for N events under nominal conditions.

- Timeboxing:
  - `task.enter_doing` results in a scheduled block in GCal or the scheduler, aligned with `time_hint`.

- Observability and permissions:
  - JSONL logs for pulls/pushes with correlation IDs; permissions enforced (`net`, `secrets.read`).
