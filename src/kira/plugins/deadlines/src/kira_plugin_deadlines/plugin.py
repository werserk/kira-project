"""Entry point for the built-in deadlines plugin."""

from __future__ import annotations

from kira.plugin_sdk.context import PluginContext


def activate(context: PluginContext) -> dict[str, str]:
    """Activate the deadlines plugin."""
    context.logger.info("Tracking upcoming deadlines")
    context.scheduler.schedule_once(
        0,
        lambda: context.logger.debug("Deadlines plugin heartbeat"),
    )
    return {"status": "ok", "plugin": "kira-deadlines"}
