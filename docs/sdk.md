# Plugin SDK Quickstart

The Kira plugin SDK provides a stable, typed interface for building plugins
without relying on private engine modules. Import helpers from
`kira.plugin_sdk` to remain forward compatible with future engine releases.

## Canonical imports

```python
from kira.plugin_sdk import context, decorators, permissions, types
```

The package exposes the following modules:

- `context` – runtime facades such as `PluginContext`, `Logger` and `EventBus`.
- `decorators` – decorators for events, commands, permissions, timeouts and retries.
- `permissions` – canonical permission names and helpers.
- `types` – public type aliases and protocols for handlers.
- `manifest` – schema helpers for `kira-plugin.json` validation.
- `rpc` – minimal RPC client abstractions.

## Minimal plugin example

The `examples/minimal-sdk-plugin` directory contains a fully working plugin
that only relies on `kira.plugin_sdk`. The main pieces look like this:

```python
from kira.plugin_sdk.context import PluginContext
from kira.plugin_sdk.decorators import command, on_event
from kira.plugin_sdk.permissions import requires


def activate(context: PluginContext) -> None:
    """Entry point executed when the plugin is loaded."""
    context.logger.info("Minimal plugin activated")


@on_event("task.created")
def handle_task_created(context: PluginContext, payload) -> None:
    context.logger.info(f"task.created payload: {payload}")
    context.events.publish("task.logged", payload)


@command("task.ping")
def ping(context: PluginContext, params) -> None:
    if requires("net", params.get("granted", [])):
        context.logger.info("Network permission granted")
    context.logger.info("pong")
```

## Manifest validation in CI

Use the manifest helpers to enforce schema compliance during continuous
integration:

```python
from kira.plugin_sdk.manifest import PluginManifestValidator

validator = PluginManifestValidator()
errors = validator.validate_manifest_file("kira-plugin.json")
if errors:
    raise SystemExit("\n".join(errors))
```

## Type checking

All public SDK modules ship with type hints compatible with `mypy --strict`.
Plugin authors can add the SDK to their type-checking pipeline to catch
integration issues early.
