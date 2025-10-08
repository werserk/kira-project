# Kira Plugin SDK Documentation

## Overview

The Kira Plugin SDK (`kira.plugin_sdk`) is the stable, public API for building plugins. It provides typed, documented facades to core capabilities while maintaining strict compatibility guarantees.

**Version:** 1.0.0  
**Status:** Stable  
**Related ADRs:** ADR-002, ADR-003, ADR-004

## Installation

Plugins are co-located in the monorepo under `src/kira/plugins/` or can be external packages. The SDK is automatically available when developing plugins.

## Quick Start

### Minimal Plugin Example

```python
# src/kira_plugin_hello/plugin.py
from kira.plugin_sdk import context, decorators

@decorators.on_event("system.ready")
def on_ready(ctx: context.PluginContext, event):
    """Handle system ready event."""
    ctx.logger.info("Hello from plugin!", event_name=event.name)
    
def activate(ctx: context.PluginContext):
    """Plugin activation entry point."""
    ctx.logger.info("Hello plugin activated")
    return {"status": "active"}
```

### Plugin Manifest

Every plugin requires a `kira-plugin.json` manifest:

```json
{
  "name": "kira-hello",
  "version": "1.0.0",
  "displayName": "Hello Plugin",
  "description": "Example hello world plugin",
  "publisher": "kira-core",
  "engines": {
    "kira": "^1.0.0"
  },
  "entry": "kira_plugin_hello.plugin:activate",
  "permissions": [
    "events.subscribe",
    "events.publish"
  ],
  "capabilities": ["pull"],
  "contributes": {
    "events": ["hello.sent"],
    "commands": []
  },
  "sandbox": {
    "strategy": "subprocess",
    "timeoutMs": 30000
  }
}
```

## SDK Modules

### 1. `kira.plugin_sdk.context`

Provides the execution context and facades for plugin operations.

#### PluginContext

Main context object passed to plugin functions.

```python
from kira.plugin_sdk.context import PluginContext

def my_handler(ctx: PluginContext):
    # Access logger
    ctx.logger.info("Processing", entity_id="task-123")
    
    # Access event bus
    ctx.events.publish("custom.event", {"data": "value"})
    
    # Access scheduler
    job_id = ctx.scheduler.schedule_interval(
        "my-job",
        60,  # Every 60 seconds
        lambda: print("Job executed")
    )
    
    # Access key-value store
    ctx.kv.set("my-key", {"value": 42})
    value = ctx.kv.get("my-key")
    
    # Access secrets (requires permission)
    api_key = ctx.secrets.get("api_key")
```

**Available Properties:**
- `logger: Logger` - Structured logging with trace IDs
- `events: EventBus` - Publish/subscribe to events
- `scheduler: Scheduler` - Schedule periodic or one-time tasks
- `kv: KeyValueStore` - Persistent key-value storage
- `secrets: SecretsManager` - Secure secrets management
- `config: dict` - Plugin configuration from manifest

### 2. `kira.plugin_sdk.decorators`

Declarative decorators for plugin functions.

#### @on_event

Subscribe to events by name.

```python
from kira.plugin_sdk import decorators

@decorators.on_event("message.received")
def handle_message(ctx, event):
    """Handle incoming messages."""
    ctx.logger.info(f"Received: {event.payload.get('text')}")
    
@decorators.on_event("task.enter_doing")
def on_task_start(ctx, event):
    """Handle task state transition."""
    task_id = event.payload["task_id"]
    ctx.logger.info(f"Task started: {task_id}")
```

#### @command

Register CLI command.

```python
@decorators.command("hello")
def hello_command(ctx, **kwargs):
    """Say hello via CLI."""
    name = kwargs.get("name", "World")
    ctx.logger.info(f"Hello, {name}!")
    return f"Hello, {name}!"
```

#### @permission

Require specific permission.

```python
@decorators.permission("net")
@decorators.permission("secrets.read")
def fetch_data(ctx):
    """Fetch data from external API."""
    api_key = ctx.secrets.get("api_key")
    # ... make network request
```

#### @timeout

Set operation timeout.

```python
@decorators.timeout(seconds=10)
def slow_operation(ctx):
    """Operation with 10s timeout."""
    # ... do work
```

#### @retry

Configure retry behavior.

```python
@decorators.retry(max_attempts=3, delay=1.0)
def flaky_operation(ctx):
    """Operation with retry logic."""
    # ... may fail and retry
```

### 3. `kira.plugin_sdk.types`

Type definitions and protocols.

```python
from kira.plugin_sdk.types import (
    EventPayload,
    CommandArguments,
    EventHandler,
    CommandHandler,
    RPCRequest,
    RPCResponse,
)

# Type-safe event handler
def my_handler(ctx: PluginContext, event: EventPayload) -> None:
    pass

# Type-safe command handler
def my_command(ctx: PluginContext, args: CommandArguments) -> str:
    return "result"
```

### 4. `kira.plugin_sdk.permissions`

Permission constants and helpers.

```python
from kira.plugin_sdk import permissions

# Permission constants
permissions.PermissionName.NET
permissions.PermissionName.FS_READ
permissions.PermissionName.FS_WRITE
permissions.PermissionName.SECRETS_READ
permissions.PermissionName.EVENTS_PUBLISH
permissions.PermissionName.SCHEDULER_CREATE

# Get all available permissions
all_perms = permissions.ALL_PERMISSIONS

# Get permission description
desc = permissions.describe("net")
# Returns: "Network access for HTTP/HTTPS requests"

# Check if permissions are granted
permissions.ensure_permissions(ctx, ["net", "secrets.read"])
```

### 5. `kira.plugin_sdk.manifest`

Manifest validation and schema access.

```python
from kira.plugin_sdk.manifest import (
    PluginManifestValidator,
    validate_plugin_manifest,
    get_manifest_schema,
)

# Validate manifest
validator = PluginManifestValidator()
result = validator.validate_manifest({
    "name": "my-plugin",
    "version": "1.0.0",
    # ... rest of manifest
})

if not result.is_valid:
    print("Validation errors:", result.errors)

# Get JSON Schema
schema = get_manifest_schema()
```

### 6. `kira.plugin_sdk.rpc`

RPC client for Host API interactions.

```python
from kira.plugin_sdk.rpc import HostRPCClient, RPCError

try:
    client = HostRPCClient(transport)
    response = client.call("vault.create_entity", {
        "entity_type": "task",
        "data": {"title": "New Task"}
    })
except RPCError as e:
    ctx.logger.error(f"RPC failed: {e}")
```

## Common Patterns

### Event-Driven Plugin

```python
from kira.plugin_sdk import context, decorators

@decorators.on_event("message.received")
def normalize_message(ctx: context.PluginContext, event):
    """Normalize incoming messages into entities."""
    text = event.payload.get("text", "")
    
    # Extract task from text
    if text.startswith("TODO:"):
        task_title = text[5:].strip()
        
        # Emit normalized event
        ctx.events.publish("inbox.normalized", {
            "entity_type": "task",
            "title": task_title,
            "source": "telegram",
            "original_event": event.correlation_id
        })
        
        ctx.logger.info(
            "Normalized message to task",
            entity_type="task",
            correlation_id=event.correlation_id
        )

def activate(ctx: context.PluginContext):
    ctx.logger.info("Normalizer plugin activated")
    return {"status": "active", "handlers": ["message.received"]}
```

### Scheduled Plugin

```python
from kira.plugin_sdk import context, decorators

def activate(ctx: context.PluginContext):
    """Activate plugin with scheduled jobs."""
    
    # Schedule sync every 5 minutes
    ctx.scheduler.schedule_interval(
        "calendar-sync",
        300,  # 5 minutes
        lambda: sync_calendar(ctx),
        job_id="calendar-sync-job"
    )
    
    # Schedule daily rollup at midnight
    ctx.scheduler.schedule_cron(
        "daily-rollup",
        "0 0 * * *",  # Every day at midnight
        lambda: generate_rollup(ctx),
        job_id="daily-rollup-job"
    )
    
    ctx.logger.info("Calendar plugin activated with scheduled jobs")
    return {"status": "active"}

def sync_calendar(ctx: context.PluginContext):
    """Sync calendar events."""
    ctx.logger.info("Starting calendar sync")
    # ... sync logic
    ctx.events.publish("calendar.synced", {"count": 10})
```

### Vault Integration

```python
from kira.plugin_sdk import context

def process_task(ctx: context.PluginContext, task_data: dict):
    """Create task in Vault via Host API."""
    
    # NOTE: In MVP, emit intent event instead of direct write
    # Future: ctx.vault.create_entity(...)
    
    ctx.events.publish("vault.create_intent", {
        "entity_type": "task",
        "data": {
            "title": task_data["title"],
            "due": task_data.get("due"),
            "priority": task_data.get("priority", "medium")
        }
    })
    
    ctx.logger.info(
        "Emitted vault create intent",
        entity_type="task",
        title=task_data["title"]
    )
```

## Best Practices

### 1. Error Handling

Always handle exceptions and log errors:

```python
@decorators.on_event("risky.operation")
def handle_risky(ctx, event):
    try:
        # ... operation that may fail
        result = process_data(event.payload)
        ctx.events.publish("operation.success", {"result": result})
    except ValueError as e:
        ctx.logger.error(f"Validation failed: {e}", error=str(e))
    except Exception as e:
        ctx.logger.error(f"Unexpected error: {e}", error=str(e), trace_id=event.trace_id)
```

### 2. Structured Logging

Use structured fields for better observability:

```python
ctx.logger.info(
    "Processing entity",
    entity_id="task-123",
    entity_type="task",
    operation="normalize",
    trace_id=event.trace_id,
    latency_ms=42.5,
    outcome="success"
)
```

### 3. Idempotency

Use stable job IDs for idempotent scheduling:

```python
# Good: stable ID, idempotent
ctx.scheduler.schedule_interval(
    "my-sync",
    60,
    sync_function,
    job_id="my-sync-job"  # Same ID = update existing job
)

# Bad: new ID every time
ctx.scheduler.schedule_interval(
    "my-sync",
    60,
    sync_function
    # No job_id = creates new job every activation
)
```

### 4. Permission Requests

Request minimal permissions needed:

```python
# Manifest
{
  "permissions": [
    "events.subscribe",
    "events.publish",
    "scheduler.create"
    // Don't request "net" if not needed
  ]
}
```

### 5. Testing

Write tests for your plugin:

```python
# tests/test_my_plugin.py
from kira.plugin_sdk.context import PluginContext
from kira_plugin_myplugin.plugin import activate, handle_event

def test_activation():
    """Test plugin activation."""
    ctx = PluginContext(config={})
    result = activate(ctx)
    assert result["status"] == "active"

def test_event_handling():
    """Test event handler."""
    ctx = PluginContext(config={})
    event = Event(name="test.event", payload={"data": "value"})
    handle_event(ctx, event)
    # Assert expected behavior
```

## Compatibility Guarantees

The SDK follows Semantic Versioning:

- **Major version** (1.x.x → 2.0.0): Breaking changes
- **Minor version** (1.0.x → 1.1.0): New features, backward compatible
- **Patch version** (1.0.0 → 1.0.1): Bug fixes, backward compatible

### Deprecation Policy

1. Feature marked as deprecated with `DeprecationWarning`
2. Alternative provided in deprecation message
3. Feature kept for ≥2 minor versions
4. Removed only in next major version

Example:
```python
# Deprecated in 1.2.0, removed in 2.0.0
@deprecated(since="1.2.0", alternative="new_method")
def old_method(ctx):
    pass
```

## Debugging

### Enable Verbose Logging

Set log level in plugin:

```python
import logging

def activate(ctx):
    ctx.logger.logger.setLevel(logging.DEBUG)
    ctx.logger.debug("Debug mode enabled")
```

### Trace Requests

Use trace IDs to follow requests:

```python
trace_id = ctx.logger.span("my_operation")
ctx.logger.info("Step 1", trace_id=trace_id)
# ... more steps
ctx.logger.info("Step 2", trace_id=trace_id)
```

### Inspect Events

Subscribe to all events for debugging:

```python
@decorators.on_event("*")
def debug_all_events(ctx, event):
    ctx.logger.debug(f"Event: {event.name}", payload=event.payload)
```

## FAQ

**Q: Can plugins import from `kira.core`?**  
A: No. Plugins must only import from `kira.plugin_sdk`. This ensures compatibility.

**Q: Can plugins import other plugins?**  
A: No. Plugins communicate via events, not direct imports.

**Q: How do I store persistent data?**  
A: Use `ctx.kv` for simple key-value storage or emit vault intents for entity creation.

**Q: Can I use external libraries?**  
A: Yes, but declare them in your plugin's dependencies.

**Q: How do I handle secrets?**  
A: Request `secrets.read`/`secrets.write` permissions and use `ctx.secrets`.

**Q: What if my operation takes a long time?**  
A: Use `@timeout` decorator or handle in background with scheduler.

## Examples

See `examples/minimal-sdk-plugin/` for a complete example plugin.

## Support

- **Documentation:** `docs/`
- **Issues:** GitHub Issues
- **ADRs:** `docs/adr/ADR-002-stable-plugin-sdk.md`

---

**Last Updated:** 2025-10-07  
**SDK Version:** 1.0.0
