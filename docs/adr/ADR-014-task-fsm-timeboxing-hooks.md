---
type: decision
id: ADR-014
title: Task FSM (todo→doing→review→done|blocked) with timeboxing hooks
date: 2025-09-19
status: accepted
owners: [kira-core, kira-plugins]
related: [ADR-001, ADR-002, ADR-005, ADR-007, ADR-009, ADR-012]
drivers: [predictability, meaningful focus, calendar alignment]
---

## Context

We need a unified task state model and automated actions on transitions to make work predictable and aligned with the calendar.

## Decision

Adopt a task FSM with explicit states and hooks:

- States: `todo → doing → review → done | blocked`.
- Transitions emit events: `task.enter_doing`, `task.enter_review`, `task.enter_done`, `task.enter_blocked`.
- Hooks:
  - `enter_doing` → schedule a timebox via scheduler/GCal (ADR-005/012), using `time_hint` if present.
  - `enter_review` → draft a review email (mailer plugin) and set `reviewer` if specified.
  - `enter_done` → update weekly rollup/KR and close timebox.
  - `enter_blocked` → optionally notify and set `blocked_reason`.

## Alternatives

- No FSM — chaotic, poor reporting. Rejected.
- Ad-hoc tags only — ambiguous semantics. Rejected.

## Implementation/Migration

1) Ontology
   - Define `.kira/ontology/fsm-task.yaml` with states, transitions, and invariants (e.g., `doing` must have an active timebox or reason).

2) Events
   - Pipelines or plugins emit transition events; consumers implement hooks as subscribers (ADR-005).

3) Plugins
   - Deadlines plugin updates due dates/snoozes; mailer plugin drafts emails; calendar plugin schedules/cancels timeboxes (ADR-012).

4) Validation
   - Host API validates allowed transitions and sets timestamps for `entered_at` fields.

## Risks

- Over-timeboxing — mitigate with policies, quotas, and user overrides.
- State drift — validate transitions; log anomalies.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Timeboxing coverage:
  - ≥90% of tasks in `doing` have an active timebox; entering `doing` without timebox requires an explicit reason.

- Event integrity:
  - Transition events are emitted with `trace_id`; hooks execute and log outcomes.

- Calendar alignment:
  - Timeboxes are created/updated/cancelled in sync with FSM events; completion closes or shortens blocks.

- Reporting:
  - Weekly rollup reflects completed tasks automatically; blocked tasks include reasons and timestamps.
