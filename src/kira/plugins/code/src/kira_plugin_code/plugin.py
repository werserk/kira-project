"""Entry point for the built-in code assistant plugin."""
from __future__ import annotations

from typing import Dict

from kira.plugin_sdk.context import PluginContext


def activate(context: PluginContext) -> Dict[str, str]:
    """Activate the code assistant plugin."""
    context.logger.info("Bootstrapping code assistant workflows")
    context.events.publish(
        "code.activate",
        {"message": "Code plugin activated", "plugin": "kira-code"},
    )
    return {"status": "ok", "plugin": "kira-code"}
