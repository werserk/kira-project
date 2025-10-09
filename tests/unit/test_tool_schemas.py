"""Unit tests for tool schemas and validation."""

from __future__ import annotations

import pytest

# Skip if pydantic not available
pytest.importorskip("pydantic")

from kira.agent.tool_schemas import (
    TOOL_SCHEMAS,
    InboxNormalizeArgs,
    RollupDailyArgs,
    TaskCreateArgs,
    TaskGetArgs,
    TaskListArgs,
    TaskUpdateArgs,
    validate_tool_args,
)


def test_task_create_args_valid() -> None:
    """Test valid task creation arguments."""
    args = TaskCreateArgs(title="Test Task", tags=["work", "urgent"])

    assert args.title == "Test Task"
    assert args.tags == ["work", "urgent"]
    assert args.due_ts is None
    assert args.assignee is None


def test_task_create_args_with_due_date() -> None:
    """Test task creation with due date."""
    args = TaskCreateArgs(
        title="Review PR",
        tags=["dev"],
        due_ts="2025-01-15T10:00:00Z",
        assignee="alice",
    )

    assert args.title == "Review PR"
    assert args.due_ts == "2025-01-15T10:00:00Z"
    assert args.assignee == "alice"


def test_task_create_args_empty_title() -> None:
    """Test task creation with empty title fails."""
    with pytest.raises(ValueError):
        TaskCreateArgs(title="")


def test_task_create_args_too_many_tags() -> None:
    """Test task creation with too many tags fails."""
    tags = [f"tag{i}" for i in range(25)]

    with pytest.raises(ValueError, match="Maximum 20 tags"):
        TaskCreateArgs(title="Test", tags=tags)


def test_task_update_args_valid() -> None:
    """Test valid task update arguments."""
    args = TaskUpdateArgs(uid="task-123", title="Updated Title", status="done")

    assert args.uid == "task-123"
    assert args.title == "Updated Title"
    assert args.status == "done"


def test_task_update_args_invalid_status() -> None:
    """Test task update with invalid status fails."""
    with pytest.raises(ValueError, match="Status must be"):
        TaskUpdateArgs(uid="task-123", status="invalid")


def test_task_get_args_valid() -> None:
    """Test valid task get arguments."""
    args = TaskGetArgs(uid="task-456")

    assert args.uid == "task-456"


def test_task_list_args_defaults() -> None:
    """Test task list with default arguments."""
    args = TaskListArgs()

    assert args.status is None
    assert args.tags == []
    assert args.limit == 50


def test_task_list_args_with_filters() -> None:
    """Test task list with filters."""
    args = TaskListArgs(status="todo", tags=["work"], limit=10)

    assert args.status == "todo"
    assert args.tags == ["work"]
    assert args.limit == 10


def test_task_list_args_invalid_status() -> None:
    """Test task list with invalid status fails."""
    with pytest.raises(ValueError, match="Status must be"):
        TaskListArgs(status="invalid")


def test_task_list_args_limit_too_large() -> None:
    """Test task list with limit too large fails."""
    with pytest.raises(ValueError):
        TaskListArgs(limit=2000)


def test_rollup_daily_args_valid() -> None:
    """Test valid rollup daily arguments."""
    args = RollupDailyArgs(date_local="2025-01-15", timezone="UTC")

    assert args.date_local == "2025-01-15"
    assert args.timezone == "UTC"


def test_rollup_daily_args_invalid_date() -> None:
    """Test rollup daily with invalid date fails."""
    with pytest.raises(ValueError, match="Invalid date format"):
        RollupDailyArgs(date_local="invalid-date")


def test_inbox_normalize_args_defaults() -> None:
    """Test inbox normalize with defaults."""
    args = InboxNormalizeArgs()

    assert args.dry_run is True
    assert args.batch_size == 10


def test_inbox_normalize_args_custom() -> None:
    """Test inbox normalize with custom values."""
    args = InboxNormalizeArgs(dry_run=False, batch_size=20)

    assert args.dry_run is False
    assert args.batch_size == 20


def test_tool_schema_registry() -> None:
    """Test tool schema registry contains all tools."""
    expected_tools = [
        "task_create",
        "task_update",
        "task_get",
        "task_list",
        "rollup_daily",
        "inbox_normalize",
    ]

    for tool_name in expected_tools:
        assert tool_name in TOOL_SCHEMAS


def test_tool_schema_get_json_schema() -> None:
    """Test getting JSON schema from tool schema."""
    schema = TOOL_SCHEMAS["task_create"]
    json_schema = schema.get_json_schema()

    assert isinstance(json_schema, dict)
    assert "type" in json_schema or "properties" in json_schema


def test_tool_schema_validate_args_success() -> None:
    """Test successful argument validation."""
    schema = TOOL_SCHEMAS["task_create"]
    args = {"title": "Test Task", "tags": ["work"]}

    validated = schema.validate_args(args)

    assert validated["title"] == "Test Task"
    assert validated["tags"] == ["work"]


def test_tool_schema_validate_args_failure() -> None:
    """Test failed argument validation."""
    schema = TOOL_SCHEMAS["task_create"]
    args = {"title": ""}  # Empty title should fail

    with pytest.raises(ValueError):
        schema.validate_args(args)


def test_validate_tool_args_success() -> None:
    """Test validate_tool_args utility function."""
    args = {"title": "Test Task", "tags": ["urgent"]}

    validated = validate_tool_args("task_create", args)

    assert validated["title"] == "Test Task"
    assert validated["tags"] == ["urgent"]


def test_validate_tool_args_unknown_tool() -> None:
    """Test validate_tool_args with unknown tool."""
    with pytest.raises(ValueError, match="Unknown tool"):
        validate_tool_args("unknown_tool", {})


def test_validate_tool_args_coercion() -> None:
    """Test argument coercion during validation."""
    args = {"uid": "task-123"}  # Minimal valid args

    validated = validate_tool_args("task_update", args)

    assert validated["uid"] == "task-123"
    # None values should be excluded
    assert "title" not in validated or validated["title"] is None

