"""JSON schema definitions and validation for agent tools.

Provides formal tool contracts with Pydantic validation.
Phase 2, Item 6: Tool registry & JSON schemas.
"""

from __future__ import annotations

from typing import Any

try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    # Fallback if pydantic not available
    BaseModel = object  # type: ignore[misc,assignment]
    Field = lambda **kwargs: None  # type: ignore[misc,assignment]
    field_validator = lambda *args, **kwargs: lambda f: f  # type: ignore[misc,assignment]

__all__ = [
    "TaskCreateArgs",
    "TaskUpdateArgs",
    "TaskGetArgs",
    "TaskListArgs",
    "RollupDailyArgs",
    "InboxNormalizeArgs",
    "ToolSchema",
    "validate_tool_args",
]


# Task tool argument schemas
class TaskCreateArgs(BaseModel):
    """Arguments for task_create tool."""

    title: str = Field(..., description="Task title", min_length=1, max_length=500)
    tags: list[str] = Field(default_factory=list, description="Task tags")
    due_ts: str | None = Field(None, description="Due timestamp (ISO 8601 format)")
    assignee: str | None = Field(None, description="Task assignee")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate tags."""
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        for tag in v:
            if not tag or len(tag) > 50:
                raise ValueError("Tag must be 1-50 characters")
        return v


class TaskUpdateArgs(BaseModel):
    """Arguments for task_update tool."""

    uid: str = Field(..., description="Task ID", min_length=1)
    title: str | None = Field(None, description="New title")
    status: str | None = Field(None, description="New status")
    assignee: str | None = Field(None, description="New assignee")
    due_ts: str | None = Field(None, description="New due timestamp")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Validate status."""
        if v and v not in ("todo", "doing", "done"):
            raise ValueError("Status must be one of: todo, doing, done")
        return v


class TaskGetArgs(BaseModel):
    """Arguments for task_get tool."""

    uid: str = Field(..., description="Task ID", min_length=1)


class TaskListArgs(BaseModel):
    """Arguments for task_list tool."""

    status: str | None = Field(None, description="Filter by status")
    tags: list[str] = Field(default_factory=list, description="Filter by tags")
    limit: int = Field(50, description="Maximum number of results", ge=1, le=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Validate status."""
        if v and v not in ("todo", "doing", "done"):
            raise ValueError("Status must be one of: todo, doing, done")
        return v


class RollupDailyArgs(BaseModel):
    """Arguments for rollup_daily tool."""

    date_local: str = Field(..., description="Local date (YYYY-MM-DD)")
    timezone: str = Field("UTC", description="Timezone")

    @field_validator("date_local")
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate date format."""
        from datetime import datetime

        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format, expected YYYY-MM-DD: {e}") from e
        return v


class InboxNormalizeArgs(BaseModel):
    """Arguments for inbox_normalize tool."""

    dry_run: bool = Field(True, description="Run in dry-run mode")
    batch_size: int = Field(10, description="Number of items to process", ge=1, le=100)


class ToolSchema:
    """Tool schema wrapper with validation."""

    def __init__(self, name: str, description: str, args_model: type[BaseModel]) -> None:
        """Initialize tool schema.

        Parameters
        ----------
        name
            Tool name
        description
            Tool description
        args_model
            Pydantic model for arguments
        """
        self.name = name
        self.description = description
        self.args_model = args_model

    def get_json_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters.

        Returns
        -------
        dict
            JSON schema
        """
        if hasattr(self.args_model, "model_json_schema"):
            return self.args_model.model_json_schema()
        # Fallback for older pydantic or when not available
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate and coerce arguments.

        Parameters
        ----------
        args
            Raw arguments

        Returns
        -------
        dict
            Validated and coerced arguments

        Raises
        ------
        ValueError
            If validation fails
        """
        try:
            validated = self.args_model(**args)
            if hasattr(validated, "model_dump"):
                return validated.model_dump(exclude_none=True)
            # Fallback
            return args
        except Exception as e:
            raise ValueError(f"Argument validation failed: {e}") from e


# Tool schema registry
TOOL_SCHEMAS: dict[str, ToolSchema] = {
    "task_create": ToolSchema("task_create", "Create a new task", TaskCreateArgs),
    "task_update": ToolSchema("task_update", "Update an existing task", TaskUpdateArgs),
    "task_get": ToolSchema("task_get", "Get a task by ID", TaskGetArgs),
    "task_list": ToolSchema("task_list", "List tasks with filters", TaskListArgs),
    "rollup_daily": ToolSchema("rollup_daily", "Generate daily rollup", RollupDailyArgs),
    "inbox_normalize": ToolSchema("inbox_normalize", "Normalize inbox items", InboxNormalizeArgs),
}


def validate_tool_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate tool arguments against schema.

    Parameters
    ----------
    tool_name
        Tool name
    args
        Raw arguments

    Returns
    -------
    dict
        Validated arguments

    Raises
    ------
    ValueError
        If tool not found or validation fails
    """
    schema = TOOL_SCHEMAS.get(tool_name)
    if not schema:
        raise ValueError(f"Unknown tool: {tool_name}")

    return schema.validate_args(args)

