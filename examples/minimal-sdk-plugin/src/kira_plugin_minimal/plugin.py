"""Minimal plugin demonstrating the stable Plugin SDK."""

from __future__ import annotations

from typing import Any

from kira.plugin_sdk.context import PluginContext
from kira.plugin_sdk.decorators import command, on_event


def activate(context: PluginContext) -> None:
    """Entry point executed when the plugin is loaded."""

    context.logger.info("Minimal plugin activated")


@on_event("task.created")
def handle_task_created(context: PluginContext, payload: dict[str, Any] | None) -> None:
    """Log a task-created event and persist it in the key/value store."""

    context.logger.info(f"task.created payload: {payload}")
    context.kv.set("last_task", payload or {})


@command("task.ping")
def ping(context: PluginContext, params: dict[str, Any] | None = None) -> None:
    """Emit a pong message and publish a follow-up event."""

    context.logger.info("pong")
    context.events.publish("task.pong", {"source": "minimal-plugin"})
