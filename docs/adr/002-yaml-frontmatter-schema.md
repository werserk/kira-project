# ADR-002: Strict YAML Front-matter Schema

## Status

**Accepted** (Phase 0, Point 2)

## Context

Kira entities are stored as Markdown files with YAML front-matter. Without a strict schema:

- **Inconsistent data**: Different files have different fields
- **Type ambiguity**: Is `tags` a string or list?
- **Timestamp chaos**: Mix of local/UTC, various formats
- **Migration nightmares**: No canonical structure to target
- **Validation gaps**: Can't validate what isn't defined

We need a **deterministic, validated schema** that ensures data consistency.

## Decision

### Strict Schema

All entities have:

**Required fields:**
- `id`: Unique entity identifier (e.g., `task-20251008-1430-fix-bug`)
- `title`: Human-readable title
- `created`: Creation timestamp (ISO-8601 UTC)
- `updated`: Last update timestamp (ISO-8601 UTC)
- `tags`: Array of tags (may be empty)

**Entity-specific fields:**
- **Task**: `status` (todo|doing|done), `assignee`, `due`, `start_ts`, `done_ts`
- **Note**: `category`, `archived`
- **Event**: `start`, `end`, `location`, `attendees`

**Optional cross-entity:**
- `links`: Array of entity IDs this links to
- `x-kira`: Sync metadata (Phase 4)

### Deterministic Serialization

```yaml
---
id: task-20251008-1430-fix-auth-bug
title: Fix authentication bug
created: 2025-10-08T14:30:00+00:00
updated: 2025-10-08T15:45:00+00:00
status: doing
tags:
  - bug
  - urgent
  - auth
---
# Task Content

Detailed description here...
```

**Rules:**
1. **Key order**: Alphabetical (for determinism)
2. **Timestamps**: ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SS+00:00`)
3. **Arrays**: YAML list format (not inline)
4. **Quoting**: Consistent (escape special chars)
5. **No local times**: All timestamps in UTC

### Round-trip Guarantee

```python
# Must be true
original = parse_entity(file)
serialized = serialize_entity(original)
reparsed = parse_entity(serialized)
assert original == reparsed
```

## Consequences

### Positive

- **Consistency**: Every file follows same structure
- **Validation**: Can validate against schema
- **Migration**: Clear target for normalization
- **Tooling**: Easy to build tools around schema
- **Git-friendly**: Deterministic serialization reduces conflicts

### Negative

- **Verbosity**: YAML front-matter can be lengthy
- **Migration cost**: Existing files need normalization
- **Rigidity**: Schema changes require migration

### Trade-offs

We choose **consistency over flexibility**. The schema is strict but evolvable through migration.

## Implementation

### Schema Definition

```python
# src/kira/core/validation.py
ENTITY_SCHEMAS = {
    "task": {
        "required": ["id", "title", "created", "updated", "status", "tags"],
        "optional": ["due", "assignee", "start_ts", "done_ts", "links"],
    },
    # ...
}
```

### Serialization

```python
# src/kira/core/yaml_serializer.py
def serialize_frontmatter(metadata: dict) -> str:
    """Deterministic YAML serialization."""
    # Sort keys, format timestamps, ensure list format
    return yaml.dump(metadata, sort_keys=True, ...)
```

## Verification

### DoD Check

```python
# Round-trip test (Phase 0, Point 2)
def test_round_trip():
    doc = parse_markdown(file)
    serialized = serialize_markdown(doc)
    reparsed = parse_markdown(serialized)
    assert doc.frontmatter == reparsed.frontmatter
```

### Tests

- `tests/unit/test_yaml_serializer.py`: Serialization tests
- `tests/unit/test_validation.py`: Schema validation
- `tests/unit/test_migration.py`: Migration to schema

## References

- Implementation: `src/kira/core/yaml_serializer.py`
- Validation: `src/kira/core/validation.py`
- Migration: `src/kira/migration/migrator.py` (Phase 8)
- Related: ADR-005 (Timezone Policy)
