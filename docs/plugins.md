# Kira Plugin Model

## Overview

Kira exposes a modular architecture where functionality can be extended via
plugins. Each plugin ships a `kira-plugin.json` manifest describing its
capabilities, permissions and configuration surface.

## Manifest structure

### Required fields

```json
{
  "name": "kira-calendar",
  "version": "0.4.2",
  "displayName": "Calendar Sync",
  "description": "Sync events & timeboxing",
  "publisher": "werserk",
  "engines": { "kira": "^1.0.0" },
  "permissions": ["calendar.write", "net", "secrets.read"],
  "entry": "kira_plugin_calendar.plugin:activate",
  "capabilities": ["pull", "push", "timebox"],
  "contributes": {
    "events": ["event.created", "task.due_soon"],
    "commands": ["calendar.pull", "calendar.push"]
  }
}
```

### Permissions

- `calendar.read/write` – calendar access.
- `vault.read/write` – secure vault access.
- `fs.read/write` – filesystem access (restricted to whitelisted paths).
- `net` – outbound network access.
- `secrets.read/write` – secrets manager access.
- `events.publish/subscribe` – event bus interactions.
- `scheduler.create/cancel` – scheduler operations.
- `sandbox.execute` – execution in the isolated sandbox.

### Capabilities

- `pull` – retrieve data from remote systems.
- `push` – push data to remote systems.
- `timebox` – manage timeboxing workflows.
- `notify` – send user notifications.
- `schedule` – schedule future tasks.
- `transform` – transform data between formats.
- `validate` – validate external payloads.
- `sync` – keep systems in sync.

## Manifest validation

### Python API

```python
from kira.plugin_sdk.manifest import PluginManifestValidator

validator = PluginManifestValidator()
errors = validator.validate_manifest_file("path/to/kira-plugin.json")

if errors:
    for error in errors:
        print(f"Validation error: {error}")
else:
    print("Manifest is valid!")
```

### Quick validation helper

```python
from kira.plugin_sdk.manifest import validate_plugin_manifest

is_valid = validate_plugin_manifest(manifest_data)
```

## Plugin configuration

Plugins can describe their configuration schema:

```json
{
  "configSchema": {
    "calendar.default": {
      "type": "string",
      "description": "Default calendar ID"
    },
    "timebox.length": {
      "type": "integer",
      "default": 90,
      "minimum": 15,
      "maximum": 480
    },
    "notifications.enabled": {
      "type": "boolean",
      "default": true
    }
  }
}
```

## Plugin isolation

### Sandbox strategies

- `subprocess` – isolated child process (default).
- `thread` – separate thread.
- `inline` – execute in the host process (for trusted plugins only).

### Sandbox configuration

```json
{
  "sandbox": {
    "strategy": "subprocess",
    "timeoutMs": 60000,
    "memoryLimit": 128,
    "networkAccess": true,
    "fsAccess": {
      "read": ["/tmp"],
      "write": ["/tmp/plugin"]
    }
  }
}
```

## Creating a plugin

1. Create a directory for the plugin.
2. Add the manifest `kira-plugin.json`.
3. Implement the entry point referenced by the manifest.
4. Validate the manifest before publishing.

### Example layout

```
my-plugin/
├── kira-plugin.json
├── src/
│   └── my_plugin/
│       ├── __init__.py
│       └── plugin.py
└── README.md
```

## Plugin SDK

Plugins interact with the host through the `PluginContext` and decorators in
the SDK:

```python
from kira.plugin_sdk.context import PluginContext
from kira.plugin_sdk.decorators import command, on_event


def activate(context: PluginContext) -> None:
    context.logger.info("Plugin activated")


@on_event("event.created")
def handle_event(context: PluginContext, event_data):
    context.logger.info(f"Received event: {event_data}")


@command("calendar.pull")
def pull_calendar(context: PluginContext, params):
    context.logger.info("Pulling calendar data")
```
