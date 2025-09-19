"""Entry point for the built-in calendar plugin."""
from __future__ import annotations

from typing import Dict

from kira.plugin_sdk.context import PluginContext


def activate(context: PluginContext) -> Dict[str, str]:
    """Activate the calendar plugin.

    Parameters
    ----------
    context:
        Execution context provided by the host application.

    Returns
    -------
    Dict[str, str]
        A status payload acknowledging activation.
    """
    context.logger.info("Activating calendar sync plugin")
    context.events.publish(
        "calendar.activate",
        {"message": "Calendar plugin activated", "plugin": "kira-calendar"},
    )
    return {"status": "ok", "plugin": "kira-calendar"}
