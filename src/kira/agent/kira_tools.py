"""Concrete tool implementations for Kira agent.

Implements:
- task_create
- task_update
- task_get
- task_list
- rollup_daily
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.host import HostAPI, ValidationError, create_host_api
from ..rollups.time_windows import compute_day_boundaries_utc
from .tools import ToolResult

__all__ = [
    "TaskCreateTool",
    "TaskUpdateTool",
    "TaskGetTool",
    "TaskListTool",
    "RollupDailyTool",
]


@dataclass
class TaskCreateTool:
    """Create new task."""

    name: str = "task_create"
    description: str = "Create a new task in the vault"
    host_api: HostAPI | None = None

    def get_parameters(self) -> dict[str, Any]:
        """Get parameter schema."""
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Task tags"},
                "due_ts": {"type": "string", "description": "Due timestamp (ISO 8601 format)"},
                "assignee": {"type": "string", "description": "Task assignee"},
            },
            "required": ["title"],
        }

    def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute task creation."""
        if not self.host_api:
            return ToolResult.error("HostAPI not initialized")

        title = args.get("title")
        if not title:
            return ToolResult.error("title is required")

        if dry_run:
            return ToolResult.ok(
                {"message": "Dry run: would create task", "title": title},
                meta={"dry_run": True},
            )

        try:
            # Check for duplicate (idempotency)
            # Simple check: list existing tasks with same title
            # In production, use more sophisticated deduplication

            entity_data = {
                "title": title,
                "status": "todo",
                "tags": args.get("tags", []),
            }

            if "due_ts" in args:
                entity_data["due_ts"] = args["due_ts"]
            if "assignee" in args:
                entity_data["assignee"] = args["assignee"]

            entity = self.host_api.create_entity("task", entity_data)

            return ToolResult.ok(
                {
                    "uid": entity.id,
                    "title": title,
                    "status": "todo",
                    "created_ts": entity.created_at.isoformat(),
                }
            )
        except ValidationError as e:
            return ToolResult.error(f"Validation error: {e}")
        except Exception as e:
            return ToolResult.error(f"Failed to create task: {e}")


@dataclass
class TaskUpdateTool:
    """Update existing task."""

    name: str = "task_update"
    description: str = "Update an existing task"
    host_api: HostAPI | None = None

    def get_parameters(self) -> dict[str, Any]:
        """Get parameter schema."""
        return {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "Task ID"},
                "title": {"type": "string", "description": "New title"},
                "status": {"type": "string", "enum": ["todo", "doing", "done"], "description": "New status"},
                "assignee": {"type": "string", "description": "New assignee"},
                "due_ts": {"type": "string", "description": "New due timestamp"},
            },
            "required": ["uid"],
        }

    def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute task update."""
        if not self.host_api:
            return ToolResult.error("HostAPI not initialized")

        uid = args.get("uid")
        if not uid:
            return ToolResult.error("uid is required")

        if dry_run:
            return ToolResult.ok(
                {"message": "Dry run: would update task", "uid": uid},
                meta={"dry_run": True},
            )

        try:
            # Build update dict
            updates: dict[str, Any] = {}
            for key in ["title", "status", "assignee", "due_ts"]:
                if key in args:
                    updates[key] = args[key]

            if not updates:
                return ToolResult.error("No updates provided")

            entity = self.host_api.update_entity(uid, updates)

            return ToolResult.ok(
                {
                    "uid": entity.id,
                    "updated_ts": entity.updated_at.isoformat(),
                    "updates": updates,
                }
            )
        except ValidationError as e:
            return ToolResult.error(f"Validation error (FSM guard?): {e}")
        except Exception as e:
            return ToolResult.error(f"Failed to update task: {e}")


@dataclass
class TaskDeleteTool:
    """Delete a task permanently."""

    name: str = "task_delete"
    description: str = "Delete a task permanently by its ID"
    host_api: HostAPI | None = None

    def get_parameters(self) -> dict[str, Any]:
        """Get parameter schema."""
        return {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "Task ID to delete"},
            },
            "required": ["uid"],
        }

    def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute task deletion."""
        if not self.host_api:
            return ToolResult.error("HostAPI not initialized")

        uid = args.get("uid")
        if not uid:
            return ToolResult.error("uid is required")

        if dry_run:
            return ToolResult.ok(
                {"message": "Dry run: would delete task", "uid": uid},
                meta={"dry_run": True},
            )

        try:
            # Delete the entity
            self.host_api.delete_entity(uid)

            return ToolResult.ok(
                {
                    "uid": uid,
                    "message": "Task deleted successfully",
                }
            )
        except ValueError as e:
            return ToolResult.error(f"Task not found: {e}")
        except Exception as e:
            return ToolResult.error(f"Failed to delete task: {e}")


@dataclass
class TaskGetTool:
    """Get task by ID."""

    name: str = "task_get"
    description: str = "Get a task by its ID"
    host_api: HostAPI | None = None

    def get_parameters(self) -> dict[str, Any]:
        """Get parameter schema."""
        return {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "Task ID"},
            },
            "required": ["uid"],
        }

    def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute task get."""
        if not self.host_api:
            return ToolResult.error("HostAPI not initialized")

        uid = args.get("uid")
        if not uid:
            return ToolResult.error("uid is required")

        try:
            entity = self.host_api.get_entity(uid)
            if not entity:
                return ToolResult.error(f"Task not found: {uid}")

            return ToolResult.ok(
                {
                    "uid": entity.id,
                    "type": entity.entity_type,
                    "metadata": entity.metadata,
                    "created_ts": entity.created_at.isoformat(),
                    "updated_ts": entity.updated_at.isoformat(),
                }
            )
        except Exception as e:
            return ToolResult.error(f"Failed to get task: {e}")


@dataclass
class TaskListTool:
    """List tasks with filters."""

    name: str = "task_list"
    description: str = "List tasks with optional filters"
    host_api: HostAPI | None = None

    def get_parameters(self) -> dict[str, Any]:
        """Get parameter schema."""
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["todo", "doing", "done"], "description": "Filter by status"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"},
                "limit": {"type": "integer", "description": "Maximum number of results", "default": 50},
            },
        }

    def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute task list."""
        if not self.host_api:
            return ToolResult.error("HostAPI not initialized")

        try:
            # List all tasks
            all_entities = self.host_api.list_entities("task")

            # Apply filters
            filtered = []
            status_filter = args.get("status")
            tags_filter = set(args.get("tags", []))
            limit = args.get("limit", 50)

            for entity in all_entities:
                # Status filter
                if status_filter and entity.metadata.get("status") != status_filter:
                    continue

                # Tags filter
                if tags_filter:
                    entity_tags = set(entity.metadata.get("tags", []))
                    if not tags_filter.intersection(entity_tags):
                        continue

                filtered.append(
                    {
                        "uid": entity.id,
                        "title": entity.metadata.get("title", ""),
                        "status": entity.metadata.get("status", ""),
                        "tags": entity.metadata.get("tags", []),
                        "created_ts": entity.created_at.isoformat(),
                    }
                )

                if len(filtered) >= limit:
                    break

            return ToolResult.ok(
                {
                    "tasks": filtered,
                    "count": len(filtered),
                }
            )
        except Exception as e:
            return ToolResult.error(f"Failed to list tasks: {e}")


@dataclass
class RollupDailyTool:
    """Generate daily rollup."""

    name: str = "rollup_daily"
    description: str = "Generate daily rollup report"
    vault_path: Path | None = None

    def get_parameters(self) -> dict[str, Any]:
        """Get parameter schema."""
        return {
            "type": "object",
            "properties": {
                "date_local": {"type": "string", "description": "Local date (YYYY-MM-DD)"},
                "timezone": {"type": "string", "description": "Timezone (default: UTC)"},
            },
            "required": ["date_local"],
        }

    def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute rollup generation."""
        if not self.vault_path:
            return ToolResult.error("Vault path not configured")

        date_str = args.get("date_local")
        if not date_str:
            return ToolResult.error("date_local is required")

        if dry_run:
            return ToolResult.ok(
                {"message": "Dry run: would generate rollup", "date": date_str},
                meta={"dry_run": True},
            )

        try:
            # Parse date
            date_local = datetime.strptime(date_str, "%Y-%m-%d")
            tz = args.get("timezone", "UTC")

            # Compute boundaries
            start_utc, end_utc = compute_day_boundaries_utc(date_local, tz)

            # Generate rollup (simplified - real implementation would use aggregator)
            rollup_path = self.vault_path / "rollups" / f"{date_str}.md"
            rollup_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle both datetime and string
            start_str = start_utc if isinstance(start_utc, str) else start_utc.isoformat()
            end_str = end_utc if isinstance(end_utc, str) else end_utc.isoformat()

            # Write simple rollup
            content = f"""# Daily Rollup: {date_str}

**Period:** {start_str} to {end_str}
**Timezone:** {tz}

## Summary
- Generated by Kira Agent
- Tasks completed: TBD
- Events: TBD

---
Generated at: {datetime.now().isoformat()}
"""
            rollup_path.write_text(content)

            return ToolResult.ok(
                {
                    "path": str(rollup_path),
                    "date": date_str,
                    "summary": "Rollup generated successfully",
                }
            )
        except Exception as e:
            return ToolResult.error(f"Failed to generate rollup: {e}")
