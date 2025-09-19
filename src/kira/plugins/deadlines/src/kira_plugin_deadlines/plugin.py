"""Entry point for the built-in deadlines plugin."""
from __future__ import annotations

from typing import Dict

from kira.plugin_sdk.context import PluginContext


def activate(context: PluginContext) -> Dict[str, str]:
    """Activate the deadlines plugin."""
    context.logger.info("Tracking upcoming deadlines")
    context.scheduler.schedule_once(
        0,
        lambda: context.logger.debug("Deadlines plugin heartbeat"),
    )
    return {"status": "ok", "plugin": "kira-deadlines"}
