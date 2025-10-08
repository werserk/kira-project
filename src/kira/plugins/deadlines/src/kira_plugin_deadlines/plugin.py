"""Deadlines Plugin with Task FSM integration (ADR-014).

Manages task deadlines, snoozes, and integrates with the Task FSM
for automated state transitions and timeboxing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kira.plugin_sdk import PluginContext

__all__ = ["activate", "get_deadlines_manager"]

_deadlines_manager: DeadlinesManager | None = None


class DeadlinesManager:
    """Manages task deadlines and FSM integration."""

    def __init__(self, context: PluginContext) -> None:
        """Initialize deadlines manager.

        Parameters
        ----------
        context
            Plugin SDK context
        """
        self.context = context
        self.logger = context.logger

        # Subscribe to FSM transition events
        context.events.subscribe("task.enter_doing", self._on_task_enter_doing)
        context.events.subscribe("task.enter_done", self._on_task_enter_done)
        context.events.subscribe("task.enter_blocked", self._on_task_enter_blocked)

        self.logger.info("DeadlinesManager initialized with FSM integration")

    def _on_task_enter_doing(self, payload: dict[str, Any]) -> None:
        """Handle task entering 'doing' state.

        Parameters
        ----------
        payload
            Event payload with task_id, timestamp, etc.
        """
        task_id = payload.get("task_id")
        if not task_id:
            return

        self.logger.info(
            f"Task {task_id} entered 'doing' state",
            extra={"task_id": task_id, "event": "task.enter_doing"},
        )

        # Update task metadata
        try:
            self._update_task_metadata(
                task_id,
                {
                    "entered_doing_at": payload.get("timestamp"),
                    "state": "doing",
                },
            )
        except Exception as exc:
            self.logger.error(
                f"Failed to update task metadata: {exc}",
                extra={"task_id": task_id, "error": str(exc)},
            )

    def _on_task_enter_done(self, payload: dict[str, Any]) -> None:
        """Handle task entering 'done' state.

        Parameters
        ----------
        payload
            Event payload
        """
        task_id = payload.get("task_id")
        if not task_id:
            return

        self.logger.info(
            f"Task {task_id} completed",
            extra={"task_id": task_id, "event": "task.enter_done"},
        )

        # Update task metadata
        try:
            self._update_task_metadata(
                task_id,
                {
                    "completed_at": payload.get("timestamp"),
                    "state": "done",
                },
            )
        except Exception as exc:
            self.logger.error(
                f"Failed to update task metadata: {exc}",
                extra={"task_id": task_id, "error": str(exc)},
            )

    def _on_task_enter_blocked(self, payload: dict[str, Any]) -> None:
        """Handle task entering 'blocked' state.

        Parameters
        ----------
        payload
            Event payload
        """
        task_id = payload.get("task_id")
        reason = payload.get("reason")

        if not task_id:
            return

        self.logger.warning(
            f"Task {task_id} blocked: {reason}",
            extra={
                "task_id": task_id,
                "event": "task.enter_blocked",
                "reason": reason,
            },
        )

        # Update task metadata
        try:
            self._update_task_metadata(
                task_id,
                {
                    "entered_blocked_at": payload.get("timestamp"),
                    "state": "blocked",
                    "blocked_reason": reason,
                },
            )
        except Exception as exc:
            self.logger.error(
                f"Failed to update task metadata: {exc}",
                extra={"task_id": task_id, "error": str(exc)},
            )

    def _update_task_metadata(self, task_id: str, metadata: dict[str, Any]) -> None:
        """Update task metadata.

        Parameters
        ----------
        task_id
            Task identifier
        metadata
            Metadata to update
        """
        # Try to use Host API
        if hasattr(self.context, "vault"):
            try:
                self.context.vault.update_entity(task_id, metadata=metadata)
                return
            except Exception:
                pass

        # Fallback: direct file update
        vault_root = self.context.config.get("vault_root", ".kira/vault")
        task_file = Path(vault_root) / "tasks" / f"{task_id}.md"

        if not task_file.exists():
            self.logger.warning(
                f"Task file not found: {task_file}",
                extra={"task_id": task_id},
            )
            return

        # Read frontmatter, update, write back
        content = task_file.read_text()
        lines = content.split("\n")

        # Find frontmatter boundaries
        if not lines[0].strip() == "---":
            self.logger.warning(f"No frontmatter in {task_file}")
            return

        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break

        if end_idx == -1:
            return

        # Parse frontmatter
        frontmatter_lines = lines[1:end_idx]
        frontmatter_text = "\n".join(frontmatter_lines)

        # Simple YAML-like update (just append new fields)
        for key, value in metadata.items():
            if isinstance(value, str):
                frontmatter_lines.append(f"{key}: {value}")
            else:
                frontmatter_lines.append(f"{key}: {json.dumps(value)}")

        # Rebuild content
        new_content = "---\n" + "\n".join(frontmatter_lines) + "\n---\n" + "\n".join(lines[end_idx + 1 :])

        task_file.write_text(new_content)

        self.logger.debug(
            f"Updated task metadata: {task_id}",
            extra={"task_id": task_id, "metadata": metadata},
        )

    def check_deadlines(self) -> list[dict[str, Any]]:
        """Check for upcoming and overdue deadlines.

        Returns
        -------
        list[dict]
            List of tasks with deadline info
        """
        # Implementation would scan vault for tasks with deadlines
        # For now, return empty list
        return []


def activate(context: PluginContext) -> dict[str, Any]:
    """Activate deadlines plugin.

    Parameters
    ----------
    context
        Plugin SDK context

    Returns
    -------
    dict
        Activation status
    """
    global _deadlines_manager

    _deadlines_manager = DeadlinesManager(context)

    context.logger.info("Deadlines plugin activated with FSM integration")

    return {
        "status": "ok",
        "plugin": "kira-deadlines",
        "features": ["fsm_integration", "deadline_tracking"],
    }


def get_deadlines_manager() -> DeadlinesManager | None:
    """Get the deadlines manager instance.

    Returns
    -------
    DeadlinesManager | None
        Manager instance if activated
    """
    return _deadlines_manager
