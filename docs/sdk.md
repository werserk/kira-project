# Kira Plugin SDK

The Kira Plugin SDK provides a stable, well-documented interface for plugin authors to interact with the Kira engine. This document serves as the primary reference for plugin development.

## Quick Start

```python
from kira.plugin_sdk import context, decorators, types

@decorators.command("hello")
def hello_command(ctx: types.PluginContext, args: types.CommandArguments) -> str:
    """A simple hello command."""
    ctx.logger.info("Hello from plugin!")
    return "Hello, World!"

@decorators.on_event("task.created")
def on_task_created(ctx: types.PluginContext, payload: types.EventPayload) -> None:
    """Handle task creation events."""
    if payload and "title" in payload:
        ctx.logger.info(f"New task: {payload['title']}")

def activate() -> dict[str, str]:
    """Plugin activation entry point."""
    return {"name": "hello-plugin", "version": "1.0.0"}
```

## Core Modules

### Context (`kira.plugin_sdk.context`)

The context module provides runtime execution context and facades for plugin authors.

#### PluginContext

The main context object passed to all plugin entry points:

```python
from kira.plugin_sdk.context import PluginContext

def my_handler(ctx: PluginContext) -> None:
    # Access configuration
    feature_flag = ctx.config.get("feature", False)

    # Use logger
    ctx.logger.info("Processing request")

    # Store data
    ctx.kv.set("last_run", "2024-01-01")

    # Schedule tasks
    ctx.scheduler.schedule_once(60, lambda: ctx.logger.info("Delayed task"))

    # Publish events
    ctx.events.publish("plugin.completed", {"status": "success"})
```

#### Available Facades

- **Logger**: Structured logging with `info()`, `warning()`, `error()`, `debug()`
- **EventBus**: Publish/subscribe to events with `publish()` and `subscribe()`
- **Scheduler**: Schedule one-time or recurring tasks
- **KeyValueStore**: Persistent key-value storage with `get()`, `set()`, `delete()`
- **SecretsManager**: Secure secret management with `get()`, `set()`, `delete()`

### Decorators (`kira.plugin_sdk.decorators`)

Decorators for defining plugin behavior:

```python
from kira.plugin_sdk.decorators import command, on_event, permission, timeout, retry

@command("process_data")
@permission("fs.read")
@timeout(30)
@retry(max_attempts=3, delay=1.0)
def process_data(ctx: PluginContext, args: CommandArguments) -> dict:
    """Process data with retry logic and timeout."""
    # Implementation here
    pass

@on_event("user.login")
def handle_user_login(ctx: PluginContext, payload: EventPayload) -> None:
    """Handle user login events."""
    # Implementation here
    pass
```

#### Available Decorators

- `@command(name)`: Register a command handler
- `@on_event(event_name)`: Register an event handler
- `@permission(perm)`: Require specific permissions
- `@timeout(seconds)`: Set execution timeout
- `@retry(max_attempts, delay)`: Add retry logic

### Types (`kira.plugin_sdk.types`)

Type definitions and protocols for plugin authors:

```python
from kira.plugin_sdk.types import (
    EventPayload,
    CommandArguments,
    PluginState,
    EventHandler,
    CommandHandler,
    RPCRequest,
    RPCResponse,
)

# Type aliases
Payload: EventPayload = {"user_id": "123", "action": "login"}
Args: CommandArguments = {"input_file": "data.csv"}

# Protocol implementations
def my_event_handler(ctx: PluginContext, payload: EventPayload) -> None:
    """Event handler implementation."""
    pass

def my_command_handler(ctx: PluginContext, args: CommandArguments) -> str:
    """Command handler implementation."""
    return "success"
```

### Permissions (`kira.plugin_sdk.permissions`)

Permission constants and helpers:

```python
from kira.plugin_sdk.permissions import (
    PermissionName,
    ALL_PERMISSIONS,
    describe,
    requires,
    ensure_permissions,
)

# Check if permission is granted
if requires("calendar.read", granted_permissions):
    ctx.logger.info("Calendar access granted")

# Get permission description
desc = describe("vault.write")
# Returns: "Write secrets to the secure vault."

# Find missing permissions
missing = ensure_permissions(
    required=["fs.read", "net"],
    granted=["fs.read"]
)
# Returns: {"net"}
```

#### Available Permissions

- `calendar.read`, `calendar.write`: Calendar access
- `vault.read`, `vault.write`: Vault access
- `fs.read`, `fs.write`: Filesystem access
- `net`: Network access
- `secrets.read`, `secrets.write`: Secrets management
- `events.publish`, `events.subscribe`: Event system
- `scheduler.create`, `scheduler.cancel`: Task scheduling
- `sandbox.execute`: Sandbox execution

### RPC (`kira.plugin_sdk.rpc`)

RPC client for host communication:

```python
from kira.plugin_sdk.rpc import HostRPCClient, RPCError

# Create RPC client (transport provided by host)
client = HostRPCClient(transport=host_transport)

try:
    result = client.call("host.get_config", {"key": "database_url"})
    ctx.logger.info(f"Config: {result}")
except RPCError as e:
    ctx.logger.error(f"RPC failed: {e}")
```

### Manifest (`kira.plugin_sdk.manifest`)

Manifest validation and schema access:

```python
from kira.plugin_sdk.manifest import (
    PluginManifestValidator,
    validate_plugin_manifest,
    get_manifest_schema,
)

# Validate manifest
validator = PluginManifestValidator()
is_valid = validator.validate_manifest_file("kira-plugin.json")

# Get schema for tooling
schema = get_manifest_schema()
```

## Plugin Development

### Plugin Structure

```
my-plugin/
├── kira-plugin.json          # Plugin manifest
└── src/
    └── my_plugin/
        ├── __init__.py
        └── plugin.py
```

### Plugin Manifest

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "A sample Kira plugin",
  "engines": {
    "kira": ">=1.0.0"
  },
  "permissions": [
    "fs.read",
    "events.publish"
  ],
  "commands": [
    "process"
  ],
  "events": [
    "file.uploaded"
  ]
}
```

### Plugin Entry Point

```python
from kira.plugin_sdk import context, decorators, types

@decorators.command("process")
def process_command(ctx: types.PluginContext, args: types.CommandArguments) -> str:
    """Process uploaded files."""
    ctx.logger.info("Processing files...")
    return "Processing complete"

@decorators.on_event("file.uploaded")
def on_file_uploaded(ctx: types.PluginContext, payload: types.EventPayload) -> None:
    """Handle file upload events."""
    if payload and "filename" in payload:
        ctx.logger.info(f"File uploaded: {payload['filename']}")

def activate() -> dict[str, str]:
    """Plugin activation entry point."""
    return {
        "name": "my-plugin",
        "version": "1.0.0",
        "description": "A sample Kira plugin"
    }
```

## Best Practices

### Import Guidelines

✅ **Do:**
```python
from kira.plugin_sdk import context, decorators, types
from kira.plugin_sdk.decorators import command, on_event
```

❌ **Don't:**
```python
from kira.core import *  # Forbidden!
import kira.core.events  # Forbidden!
```

### Error Handling

```python
from kira.plugin_sdk.rpc import RPCError

def safe_operation(ctx: PluginContext) -> None:
    try:
        result = ctx.rpc.call("risky_operation")
        ctx.logger.info(f"Success: {result}")
    except RPCError as e:
        ctx.logger.error(f"RPC failed: {e}")
        # Handle gracefully
    except Exception as e:
        ctx.logger.error(f"Unexpected error: {e}")
        raise
```

### Async Support

```python
import asyncio
from kira.plugin_sdk.types import EventHandler

async def async_handler(ctx: PluginContext, payload: EventPayload) -> None:
    """Async event handler."""
    await asyncio.sleep(1)  # Simulate async work
    ctx.logger.info("Async operation completed")

# Register async handler
ctx.events.subscribe("async.event", async_handler)
```

## Compatibility

The SDK follows semantic versioning:

- **Major version changes**: Breaking changes requiring plugin updates
- **Minor version changes**: New features, backward compatible
- **Patch version changes**: Bug fixes, backward compatible

Plugins declare required engine version in their manifest:

```json
{
  "engines": {
    "kira": ">=1.0.0,<2.0.0"
  }
}
```

## Examples

See the `examples/` directory for complete plugin examples demonstrating SDK usage patterns.

## Support

For questions and support:

- Check the [Architecture Decision Records](../adr/) for design rationale
- Review existing plugins in `src/kira/plugins/`
- Run tests with `poetry run pytest tests/unit/test_sdk_surface.py`
