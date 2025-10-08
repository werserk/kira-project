# Naming Conventions and ID Guidelines (ADR-008)

## Overview

Kira uses stable, human-meaningful identifiers for all entities. This document describes the naming conventions, ID format, and best practices.

## ID Format

### Standard Format

```
<kind>-YYYYMMDD-HHmm-<slug>
```

**Components:**
- **kind**: Entity type (lowercase kebab-case: `task`, `note`, `event`, etc.)
- **YYYYMMDD**: Date in configured timezone (default: Europe/Brussels)
- **HHmm**: Time in 24-hour format
- **slug**: URL-safe slug from title (kebab-case)

### Examples

```
task-20250115-1430-fix-auth-bug
note-20250115-0920-meeting-summary
event-20250120-1000-team-standup
project-20250101-0900-mobile-app-v2
```

## Entity Types

### Core Types

| Type | Prefix | Description | Example |
|------|--------|-------------|---------|
| **task** | `task-` | Actionable items | `task-20250115-1430-implement-login` |
| **note** | `note-` | Information capture | `note-20250115-1200-architecture-notes` |
| **event** | `event-` | Calendar events | `event-20250120-1000-quarterly-review` |
| **meeting** | `meeting-` | Meeting notes | `meeting-20250115-1400-team-sync` |
| **project** | `project-` | Larger initiatives | `project-20250110-0900-auth-refactor` |
| **contact** | `contact-` | People/organizations | `contact-20250115-john-doe` |

### Custom Types

Register new entity types:

```python
from kira.core.ids import register_entity_type

register_entity_type("resource")  # Must be lowercase, 2-20 chars
```

## Slug Generation

### Rules

1. **Lowercase only**: All uppercase → lowercase
2. **ASCII safe**: Unicode → closest ASCII or removed
3. **Hyphen separated**: Spaces and special chars → hyphens
4. **Collapsed hyphens**: Multiple hyphens → single hyphen
5. **No leading/trailing**: Trim hyphens from edges
6. **Length limit**: Maximum 50 characters in slug part

### Examples

| Input Title | Generated Slug |
|-------------|---------------|
| "Fix Authentication Bug" | `fix-authentication-bug` |
| "Meeting: Q1 Planning" | `meeting-q1-planning` |
| "User Story #42" | `user-story-42` |
| "Встреча с клиентом" | `vstretcha-s-klientom` (transliterated) |

### Implementation

```python
from kira.core.ids import generate_entity_id

# With title
entity_id = generate_entity_id("task", title="Fix Authentication Bug")
# → task-20250115-1430-fix-authentication-bug

# Without title (generates short UUID)
entity_id = generate_entity_id("note")
# → note-20250115-1430-a1b2c3d4
```

## Timezone Handling

### Default Timezone

Per ADR-008, the default timezone is **Europe/Brussels**.

Configure in `kira.yaml`:

```yaml
vault:
  path: "/path/to/vault"
  tz: "Europe/Brussels"  # Your timezone
```

### Supported Timezones

Any IANA timezone identifier:
- `Europe/Brussels`
- `America/New_York`
- `Asia/Tokyo`
- `UTC`

### Examples

```python
from kira.core.ids import generate_entity_id
from datetime import datetime, timezone

# Use default timezone
id1 = generate_entity_id("task", title="Test")

# Specify timezone
id2 = generate_entity_id("task", title="Test", tz="America/New_York")

# Specify timestamp
ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
id3 = generate_entity_id("task", title="Test", timestamp=ts, tz="Europe/Brussels")
```

## Collision Detection

### Automatic Handling

The system prevents ID collisions automatically:

```python
from kira.core.ids import CollisionDetector

detector = CollisionDetector()

# First ID
id1 = detector.generate_unique_id("task", "Test Task")
detector.register_id(id1)
# → task-20250115-1430-test-task

# Second ID with same title (collision)
id2 = detector.generate_unique_id("task", "Test Task")
# → task-20250115-1430-test-task-2
```

### Manual Collision Resolution

If you need to handle collisions manually:

1. **Add numeric suffix**: `task-20250115-1430-test-2`
2. **Modify slug**: `task-20250115-1430-test-revised`
3. **Change timestamp**: Wait a minute and regenerate

## Filename Mapping

### Rule

Every entity ID maps to a filename:

```
{entity-id}.md
```

### Examples

| Entity ID | Filename |
|-----------|----------|
| `task-20250115-1430-fix-bug` | `task-20250115-1430-fix-bug.md` |
| `note-research-patterns` | `note-research-patterns.md` |

### Directory Structure

Combined with folder contracts:

```
vault/
├── tasks/
│   ├── task-20250115-1430-fix-auth.md
│   └── task-20250115-1530-update-docs.md
├── notes/
│   ├── note-20250115-0900-daily-standup.md
│   └── note-20250115-1200-research-notes.md
└── projects/
    └── project-20250110-0900-mobile-app.md
```

## Alias Tracking (Migration)

### Purpose

Track old IDs during migration to maintain backward compatibility.

### Usage

```python
from kira.core.ids import AliasTracker

# Initialize tracker
tracker = AliasTracker(aliases_file=Path("vault/.kira/aliases.json"))

# Add alias during migration
tracker.add_alias("old-task-id", "task-20250115-1430-migrated")

# Resolve old IDs
current_id = tracker.resolve_id("old-task-id")
# → task-20250115-1430-migrated

# Get all aliases for current ID
aliases = tracker.get_aliases("task-20250115-1430-migrated")
# → ["old-task-id"]

# Save aliases
tracker.save_aliases()
```

### Migration Workflow

1. **Scan existing entities** and collect IDs
2. **Generate new IDs** following ADR-008 format
3. **Create alias mappings** (old → new)
4. **Update wikilinks** in content using aliases
5. **Rename files** to new format
6. **Save alias map** for future reference

## Best Practices

### ✅ DO

- **Use descriptive titles**: Titles become slugs in IDs
- **Be consistent**: Same timezone across all operations
- **Let system generate IDs**: Don't create IDs manually
- **Use Host API**: Creates IDs automatically with validation
- **Keep titles under 50 chars**: For reasonable slug length

### ❌ DON'T

- **Don't use special characters in titles**: They're stripped in slugs
- **Don't rely on specific timestamp**: IDs may change if recreated
- **Don't create IDs manually**: Use `generate_entity_id()`
- **Don't bypass collision detection**: Always check uniqueness

## Validation

### Validate ID Format

```python
from kira.core.ids import is_valid_entity_id, validate_entity_id

# Check if valid
if is_valid_entity_id("task-20250115-1430-test"):
    print("Valid ID")

# Validate and normalize
try:
    normalized = validate_entity_id("task-20250115-1430-test")
except ValueError as e:
    print(f"Invalid ID: {e}")
```

### CLI Validation

```bash
# Validate entire Vault
make vault-validate

# Check Vault info
make vault-info
```

## Searchability

### By ID

IDs are designed for easy searching:

```bash
# Find entity by ID
grep -r "task-20250115-1430-test" vault/

# Find all tasks from date
grep -r "task-20250115-" vault/tasks/

# Find entities by slug
grep -r "fix-auth-bug" vault/
```

### In Code

```python
from kira.core.host import create_host_api

host_api = create_host_api("vault/")

# Read by ID
entity = host_api.read_entity("task-20250115-1430-test")

# List by type
tasks = list(host_api.list_entities("task"))
```

## Determinism

### Same Inputs → Same ID

Given the same:
- Entity type
- Title
- Minute (timestamp rounded to minute)
- Timezone

The system generates the **same ID**.

### Example

```python
from datetime import datetime, timezone
from kira.core.ids import generate_entity_id

ts = datetime(2025, 1, 15, 14, 30, 45, tzinfo=timezone.utc)  # 45 seconds

id1 = generate_entity_id("task", title="Test", timestamp=ts)
id2 = generate_entity_id("task", title="Test", timestamp=ts)

assert id1 == id2  # ✅ Same ID
```

### Changing Title Changes Slug Only

```python
id1 = generate_entity_id("task", title="Original Title", timestamp=ts)
id2 = generate_entity_id("task", title="Updated Title", timestamp=ts)

# type-YYYYMMDD-HHmm part is same, only slug differs
assert id1.split("-")[:3] == id2.split("-")[:3]
```

## FAQ

### Q: Can I use custom IDs?

**A:** Yes, but they must follow the format. Use `custom_suffix`:

```python
entity_id = generate_entity_id("task", custom_suffix="my-custom-identifier")
# → task-20250115-1430-my-custom-identifier
```

### Q: What if two entities have the same title at the same time?

**A:** Use `CollisionDetector` which adds numeric suffixes:

```python
detector = CollisionDetector()

id1 = detector.generate_unique_id("task", "Same Title")
detector.register_id(id1)
# → task-20250115-1430-same-title

id2 = detector.generate_unique_id("task", "Same Title")
# → task-20250115-1430-same-title-2
```

### Q: How do I migrate old IDs?

**A:** Use `AliasTracker` to maintain backward compatibility:

1. Generate new ID
2. Add alias mapping
3. Update references
4. Save alias map

### Q: What characters are allowed in IDs?

**A:** Only lowercase letters, numbers, and hyphens: `[a-z0-9-]`

### Q: How long can IDs be?

**A:** Maximum 100 characters (filesystem safety per ADR-008).

### Q: Can I change an entity's ID?

**A:** Technically yes, but discouraged. Better to:
1. Create new entity with desired ID
2. Copy content
3. Delete old entity
4. Add alias mapping

## Integration Examples

### Creating Entity via Host API

```python
from kira.core.host import create_host_api

host_api = create_host_api("vault/")

# ID generated automatically
entity = host_api.create_entity(
    "task",
    {
        "title": "Implement User Authentication",
        "status": "todo",
        "priority": "high",
    },
    content="Detailed task description..."
)

print(f"Created: {entity.id}")
# → task-20250115-1430-implement-user-authentication
```

### Creating Entity via CLI

```bash
# Generate ID automatically
./kira vault new --type task --title "Fix Bug in API"

# Show template only
./kira vault new --type note --title "Research Notes" --template
```

### Using in Plugins

```python
from kira.plugin_sdk.context import PluginContext
from kira.core.ids import generate_entity_id

def my_plugin_function(context: PluginContext):
    # Generate ID
    entity_id = generate_entity_id("task", title="Auto-generated task")

    # Create via Vault API (if available)
    if context.vault:
        entity = context.vault.create_entity(
            "task",
            {
                "id": entity_id,
                "title": "Auto-generated task",
                "status": "todo",
            }
        )
```

## References

- **ADR-008**: Stable identifiers and naming rules
- **ADR-006**: Vault Host API
- **ADR-007**: Schemas & Folder-Contracts
- **docs/plugins.md**: Plugin development guide
