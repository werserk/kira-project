# Tasks Folder Contract

This folder contains task entities following the Task FSM (ADR-014).

## Allowed Entity Types

- `task` - Regular tasks with FSM lifecycle

## Naming Convention

Files must follow the pattern: `task-YYYYMMDD-HHmm-slug.md`

Example: `task-20250107-1430-fix-authentication-bug.md`

## Required Frontmatter Fields

All tasks must include:

- `id` - Unique task identifier (format: task-YYYYMMDD-HHmm-slug)
- `title` - Task title
- `status` - One of: todo, doing, review, done, blocked
- `created` - Creation timestamp (ISO 8601)
- `updated` - Last update timestamp (ISO 8601)

## Optional Frontmatter Fields

- `priority` - Priority level: low, medium, high, urgent
- `due` - Due date (ISO 8601)
- `time_hint` - Estimated duration in minutes
- `project` - Parent project ID
- `depends_on` - Array of task IDs this depends on
- `blocks` - Array of task IDs this blocks
- `tags` - Array of tags
- `gcal_event_id` - Google Calendar event ID (for timeboxed tasks)
- `blocked_reason` - Reason for blocked status (required if status=blocked)
- `completed_at` - Completion timestamp
- `source` - Source of task creation

## FSM Transitions

Tasks follow a finite state machine (ADR-014):

```
todo → doing → review → done
  ↓       ↓        ↓
  └─── blocked ───┘
```

### State Rules

- **todo**: Initial state for new tasks
- **doing**: Task is being actively worked on
  - Creates timebox in calendar if `time_hint` provided
  - Requires active timebox or explicit reason
- **review**: Task needs review before completion
  - Optionally triggers review email draft
- **done**: Task is completed
  - Records `completed_at` timestamp
  - Closes timebox if present
- **blocked**: Task cannot proceed
  - Requires `blocked_reason` in frontmatter
  - Optionally sends notification

## Examples

### Minimal Task

```yaml
---
id: task-20250107-1430-example
title: Example task
status: todo
created: 2025-01-07T14:30:00+01:00
updated: 2025-01-07T14:30:00+01:00
---

Task description goes here.
```

### Full Task

```yaml
---
id: task-20250107-1430-implement-feature
title: Implement new feature
status: doing
priority: high
due: 2025-01-10T17:00:00+01:00
time_hint: 120
project: project-20250101-0900-q1-goals
depends_on:
  - task-20250106-1000-design-review
tags:
  - backend
  - api
gcal_event_id: abc123xyz
created: 2025-01-07T14:30:00+01:00
updated: 2025-01-07T15:45:00+01:00
source: telegram
---

## Description

Implement the new authentication feature as discussed in the design review.

## Acceptance Criteria

- [ ] Backend API endpoints created
- [ ] Unit tests written
- [ ] Integration tests passing
- [ ] Documentation updated

## Notes

Need to coordinate with @alice for database schema changes.
```

## Validation

Tasks are validated against the schema at `.kira/schemas/task.json`.

To validate manually:

```bash
make vault-validate
```

Or via CLI:

```bash
kira vault validate --type task
```

## Links

Related entities can be referenced using wikilinks: `[[entity-id]]` or mentions: `@entity-id`

## See Also

- [ADR-014: Task FSM](../../docs/adr/ADR-014-task-fsm-timeboxing-hooks.md)
- [ADR-007: Schemas & Folder Contracts](../../docs/adr/ADR-007-schemas-folder-contracts-single-source.md)
- [ADR-008: Stable Identifiers](../../docs/adr/ADR-008-ids-naming-conventions.md)

