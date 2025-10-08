# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) documenting key architectural decisions in the Kira project.

## ADR Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](001-single-writer-pattern.md) | Single Writer Pattern via Host API | Accepted |
| [ADR-002](002-yaml-frontmatter-schema.md) | Strict YAML Front-matter Schema | Accepted |
| [ADR-003](003-event-idempotency.md) | Event Idempotency Keys | Accepted |
| [ADR-004](004-event-envelope.md) | Standardized Event Envelope | Accepted |
| [ADR-005](005-timezone-policy.md) | UTC Time Discipline | Accepted |
| [ADR-006](006-gcal-sync-policy.md) | Two-Way GCal Sync Policy | Accepted |
| [ADR-007](007-plugin-sandbox.md) | Plugin Sandbox Security | Accepted |

## ADR Format

Each ADR follows this structure:

1. **Title**: Short, descriptive name
2. **Status**: Proposed, Accepted, Deprecated, Superseded
3. **Context**: What is the issue we're addressing?
4. **Decision**: What is the change we're proposing/making?
5. **Consequences**: What becomes easier or harder?
6. **References**: Links to related documents, code, or discussions

## Creating a New ADR

1. Copy the template: `cp template.md XXX-short-title.md`
2. Fill in the sections
3. Submit for review
4. Update this README with the new ADR

## Reading Order for New Developers

For onboarding, read ADRs in this order:

1. **ADR-001**: Single Writer Pattern - Foundation of data consistency
2. **ADR-002**: YAML Schema - Data structure and serialization
3. **ADR-005**: Timezone Policy - Time handling discipline
4. **ADR-003**: Event Idempotency - Reliable event processing
5. **ADR-004**: Event Envelope - Event structure standard
6. **ADR-006**: GCal Sync Policy - Two-way sync without echo loops
7. **ADR-007**: Plugin Sandbox - Security model

Total reading time: ~20 minutes