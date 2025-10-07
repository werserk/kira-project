# Vault API for Plugins (ADR-006)

This guide explains how plugins should interact with the Vault through the Host API instead of direct filesystem access.

## Overview

Per **ADR-006**, all Vault mutations must go through the Host API to ensure:
- **Schema validation** against `.kira/schemas/*.json`
- **ID generation and collision prevention** following ADR-008 conventions
- **Link graph maintenance** for consistent references (ADR-016)
- **Event emission** for `entity.created`, `entity.updated`, `entity.deleted`
- **Atomic file operations** preventing data corruption

**Direct filesystem writes to the Vault are explicitly forbidden by sandbox policy.**

## Quick Start

### Accessing the Vault API

Plugins access the Vault through `context.vault`:

```python
from kira.plugin_sdk.context import PluginContext

def my_plugin_function(context: PluginContext):
    # Always check if vault is available
    if context.vault is None:
        context.logger.warning("Vault API not available")
        return

    # Use context.vault for all Vault operations
    entity = context.vault.create_entity(
        "task",
        {"title": "My Task", "priority": "high"},
        content="Task description"
    )
    context.logger.info(f"Created entity: {entity.id}")
```

### Basic Operations

#### Create Entity

```python
entity = context.vault.create_entity(
    entity_type="task",  # Type: task, note, event, meeting, project, etc.
    data={
        "title": "Fix authentication bug",
        "priority": "high",
        "status": "todo",
        "tags": ["bug", "auth"]
    },
    content="# Fix authentication bug\n\nDetailed description here"
)

print(f"Created: {entity.id}")  # e.g., task-20250107-1430-fix-authentication-bug
print(f"Path: {entity.path}")   # Path to file in Vault
```

#### Read Entity

```python
entity = context.vault.read_entity("task-20250107-1430-fix-bug")

title = entity.metadata.get("title")
status = entity.metadata.get("status")
content = entity.content
```

#### Update Entity

```python
updated = context.vault.update_entity(
    entity_id="task-20250107-1430-fix-bug",
    updates={
        "status": "done",
        "completed_at": "2025-01-07T15:00:00Z"
    },
    content="# Fix authentication bug\n\nCompleted successfully"
)
```

#### Delete Entity

```python
context.vault.delete_entity("task-20250107-1430-obsolete-task")
```

#### List Entities

```python
# List all entities
all_entities = context.vault.list_entities()

# List entities by type
tasks = context.vault.list_entities("task", limit=10)

for task in tasks:
    print(f"{task.id}: {task.metadata.get('title')}")
```

#### Search Entities

```python
# Search in titles and content
results = context.vault.search_entities(
    query="urgent",
    entity_type="task",  # Optional filter
    limit=20
)

for entity in results:
    print(f"Found: {entity.metadata.get('title')}")
```

#### Upsert Entity

Create or update based on whether ID exists:

```python
# Creates new entity if id not present
entity = context.vault.upsert_entity(
    "task",
    {"title": "New or Updated Task"},
    content="Content"
)

# Updates existing if id present
entity = context.vault.upsert_entity(
    "task",
    {"id": "task-123", "title": "Updated Task"},
    content="Updated content"
)
```

#### Get Entity Links

```python
links = context.vault.get_entity_links("task-123")

# Outgoing links (this entity → others)
for link in links["outgoing"]:
    print(f"Links to: {link['target_id']}")

# Incoming links (others → this entity)
for link in links["incoming"]:
    print(f"Linked from: {link['source_id']}")
```

## Entity Types

Standard entity types (defined in `.kira/schemas/`):

| Type | Description | Example Title |
|------|-------------|---------------|
| `task` | Actionable work item | "Implement feature X" |
| `note` | Knowledge/observation | "Meeting notes 2025-01-07" |
| `event` | Calendar event | "Team standup" |
| `meeting` | Meeting with attendees | "Q1 planning meeting" |
| `project` | Long-term project | "Auth system redesign" |
| `contact` | Person/organization | "John Doe" |

## Entity Metadata

Common metadata fields:

```python
{
    "id": "task-20250107-1430-example",  # Auto-generated if not provided
    "title": "Task title",                # Required for most types
    "status": "todo",                     # task: todo/doing/review/done/blocked
    "priority": "high",                   # high/medium/low
    "tags": ["bug", "urgent"],           # List of tags
    "due": "2025-01-15",                 # ISO date for deadline
    "depends_on": ["task-123"],          # IDs of dependencies
    "assigned_to": ["contact-456"],      # Assigned contacts
    "created": "2025-01-07T14:30:00Z",   # Auto-managed by Host API
    "updated": "2025-01-07T14:30:00Z"    # Auto-managed by Host API
}
```

## Error Handling

```python
from kira.core.host import EntityNotFoundError, VaultError

try:
    entity = context.vault.read_entity("nonexistent-id")
except EntityNotFoundError as e:
    context.logger.error(f"Entity not found: {e}")
except VaultError as e:
    context.logger.error(f"Vault operation failed: {e}")
```

## Events

Vault operations emit events that plugins can subscribe to:

```python
def on_entity_created(context: PluginContext, event_data):
    entity_id = event_data.get("entity_id")
    entity_type = event_data.get("entity_type")
    context.logger.info(f"New {entity_type} created: {entity_id}")

# Subscribe to events
context.events.subscribe("entity.created", on_entity_created)
context.events.subscribe("entity.updated", on_entity_updated)
context.events.subscribe("entity.deleted", on_entity_deleted)
```

Event payloads:

- `entity.created`: `{"entity_id": str, "entity_type": str, "path": str}`
- `entity.updated`: `{"entity_id": str, "entity_type": str, "path": str}`
- `entity.deleted`: `{"entity_id": str, "entity_type": str}`

## Complete Plugin Example

```python
"""Example plugin demonstrating proper Vault API usage."""

from kira.plugin_sdk.context import PluginContext

def activate(context: PluginContext) -> dict[str, str]:
    """Plugin activation with vault access."""
    if context.vault is None:
        context.logger.warning("Vault API not available")
        return {"status": "error", "reason": "no_vault"}

    context.logger.info("Plugin activated with Vault access")
    return {"status": "ok"}

def handle_message_received(context: PluginContext, event_data: dict) -> None:
    """Process incoming message and create Vault entity."""
    message = event_data.get("message", "")
    source = event_data.get("source", "unknown")

    # Check vault availability
    if context.vault is None:
        context.logger.warning("Cannot process message: Vault not available")
        return

    try:
        # Extract title from message (first line or beginning)
        title = message.split("\n")[0][:100]

        # Create entity via Host API
        entity = context.vault.create_entity(
            entity_type="note",
            data={
                "title": title,
                "source": source,
                "status": "inbox",
                "tags": ["inbox", "unprocessed"]
            },
            content=message
        )

        context.logger.info(f"Created inbox item: {entity.id}")

        # Emit custom event for downstream processing
        context.events.publish("inbox.item_created", {
            "entity_id": entity.id,
            "source": source
        })

    except Exception as exc:
        context.logger.error(f"Failed to create entity: {exc}")

def process_task_completion(context: PluginContext, task_id: str) -> None:
    """Update task status to done."""
    if context.vault is None:
        return

    try:
        # Read current state
        task = context.vault.read_entity(task_id)

        # Update status
        context.vault.update_entity(
            task_id,
            {
                "status": "done",
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
        )

        context.logger.info(f"Task {task_id} marked as done")

    except EntityNotFoundError:
        context.logger.error(f"Task not found: {task_id}")
```

## Permissions

Plugins must declare `vault.read` and/or `vault.write` permissions in their manifest:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "permissions": [
    "vault.read",
    "vault.write",
    "events.subscribe",
    "events.publish"
  ],
  "sandbox": {
    "strategy": "subprocess",
    "fsAccess": {
      "read": [],
      "write": []
    }
  }
}
```

**Note:** Even with `fs.read` and `fs.write` permissions, **direct access to Vault paths is denied** by sandbox policy. Always use `context.vault`.

## Why Not Direct Filesystem Access?

❌ **Don't do this** (forbidden by sandbox):

```python
# WRONG: Direct filesystem write
with open("vault/tasks/my-task.md", "w") as f:
    f.write("---\ntitle: My Task\n---\n\nContent")
```

**Problems:**
- No schema validation
- No ID generation/collision check
- Link graph not updated
- No events emitted
- Potential file corruption
- Violates sandbox policy (will fail)

✅ **Do this** (correct pattern):

```python
# CORRECT: Use Host API
entity = context.vault.create_entity(
    "task",
    {"title": "My Task"},
    content="Content"
)
```

**Benefits:**
- Schema validation ensures data integrity
- IDs auto-generated following conventions
- Links automatically maintained
- Events emitted for subscribers
- Atomic operations prevent corruption
- Respects sandbox security

## Testing

Test your plugin with Vault API:

```python
import pytest
from pathlib import Path
from kira.core.host import create_host_api
from kira.core.vault_facade import create_vault_facade
from kira.plugin_sdk.context import PluginContext

def test_my_plugin_with_vault(tmp_path):
    # Setup Host API
    host_api = create_host_api(tmp_path)
    vault = create_vault_facade(host_api)

    # Create plugin context with vault
    context = PluginContext(
        config={"vault": {"path": str(tmp_path)}},
        vault=vault
    )

    # Test your plugin function
    from my_plugin import handle_message_received
    handle_message_received(context, {"message": "Test message"})

    # Verify entity was created
    entities = vault.list_entities("note")
    assert len(entities) == 1
    assert entities[0].metadata["title"] == "Test message"
```

## RPC Methods (Subprocess Plugins)

When plugins run in subprocess sandbox, Vault operations are executed via JSON-RPC:

| RPC Method | Description |
|------------|-------------|
| `vault.create` | Create entity |
| `vault.read` | Read entity by ID |
| `vault.update` | Update entity |
| `vault.delete` | Delete entity |
| `vault.list` | List entities |
| `vault.upsert` | Create or update |
| `vault.get_links` | Get entity links |
| `vault.search` | Search entities |

The `context.vault` facade automatically handles RPC calls when running in subprocess mode.

## Best Practices

1. **Always check availability**: `if context.vault is None`
2. **Handle exceptions**: Catch `EntityNotFoundError`, `VaultError`
3. **Use type hints**: Type safety helps catch errors
4. **Validate inputs**: Check required fields before creating entities
5. **Emit events**: Publish custom events for downstream processing
6. **Log operations**: Use `context.logger` for debugging
7. **Test with real Vault**: Integration tests with `create_host_api`
8. **Follow ID conventions**: Let Host API generate IDs (ADR-008)
9. **Respect schema**: Follow `.kira/schemas/*.json` definitions
10. **Atomic operations**: Use `upsert` for idempotent updates

## Troubleshooting

### "Vault API not available"

**Problem:** `context.vault is None`

**Solution:** Ensure Host API is initialized and injected into context:

```python
from kira.core.host import create_host_api
from kira.core.vault_facade import create_vault_facade

host_api = create_host_api(vault_path)
vault = create_vault_facade(host_api)
context = PluginContext(vault=vault)
```

### "Direct Vault writes forbidden"

**Problem:** Sandbox policy denies filesystem write to Vault path

**Solution:** Use `context.vault` API instead of direct `open()` or `Path.write_text()`

### "Invalid entity ID"

**Problem:** Manually constructed ID doesn't match ADR-008 format

**Solution:** Let Host API generate IDs automatically by not providing `id` in data

### "Schema validation failed"

**Problem:** Entity data doesn't match schema in `.kira/schemas/`

**Solution:** Check schema requirements and ensure all required fields are present

## Related Documentation

- [ADR-006: Vault Host API](../docs/adr/ADR-006-vault-host-api-no-direct-fs.md)
- [ADR-007: Schemas & Folder Contracts](../docs/adr/ADR-007-schemas-folder-contracts-single-source.md)
- [ADR-008: IDs & Naming Conventions](../docs/adr/ADR-008-ids-naming-conventions.md)
- [Plugin SDK Reference](../docs/sdk.md)
- [Host API Reference](../src/kira/core/host.py)

## Summary

**Key Takeaway:** Always use `context.vault` for Vault operations. Direct filesystem access is forbidden and will fail in production sandbox.

```python
# ✅ Correct
entity = context.vault.create_entity("task", data, content)

# ❌ Wrong (will fail)
Path("vault/tasks/file.md").write_text(content)
```

