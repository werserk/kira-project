"""Entry point for the built-in mailer plugin."""
from __future__ import annotations

from typing import Dict

from kira.plugin_sdk.context import PluginContext


def activate(context: PluginContext) -> Dict[str, str]:
    """Activate the mailer plugin."""
    context.logger.info("Preparing outbound notifications")
    context.events.publish(
        "mailer.activate",
        {"message": "Mailer plugin activated", "plugin": "kira-mailer"},
    )
    return {"status": "ok", "plugin": "kira-mailer"}
