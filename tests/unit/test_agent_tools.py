"""Unit tests for agent tools."""

from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from kira.agent.kira_tools import RollupDailyTool, TaskCreateTool, TaskGetTool, TaskListTool, TaskUpdateTool
from kira.agent.tools import ToolRegistry, ToolResult


class TestToolResult:
    """Tests for ToolResult."""

    def test_ok_result(self):
        """Test creating OK result."""
        result = ToolResult.ok({"key": "value"}, meta={"trace_id": "123"})

        assert result.status == "ok"
        assert result.data == {"key": "value"}
        assert result.meta["trace_id"] == "123"

        result_dict = result.to_dict()
        assert result_dict["status"] == "ok"
        assert result_dict["data"]["key"] == "value"

    def test_error_result(self):
        """Test creating error result."""
        result = ToolResult.error("Something failed")

        assert result.status == "error"
        assert result.error == "Something failed"

        result_dict = result.to_dict()
        assert result_dict["status"] == "error"
        assert result_dict["error"] == "Something failed"


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get_tool(self):
        """Test tool registration and retrieval."""
        registry = ToolRegistry()

        # Create mock tool
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"

        registry.register(mock_tool)

        # Retrieve tool
        tool = registry.get("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

    def test_get_nonexistent_tool(self):
        """Test getting non-existent tool."""
        registry = ToolRegistry()
        tool = registry.get("nonexistent")
        assert tool is None

    def test_list_tools(self):
        """Test listing all tools."""
        registry = ToolRegistry()

        mock_tool1 = Mock()
        mock_tool1.name = "tool1"
        mock_tool2 = Mock()
        mock_tool2.name = "tool2"

        registry.register(mock_tool1)
        registry.register(mock_tool2)

        tools = registry.list_tools()
        assert len(tools) == 2


class TestTaskCreateTool:
    """Tests for TaskCreateTool."""

    def test_get_parameters(self):
        """Test parameter schema."""
        tool = TaskCreateTool()
        params = tool.get_parameters()

        assert params["type"] == "object"
        assert "title" in params["properties"]
        assert "title" in params["required"]

    def test_execute_dry_run(self):
        """Test dry run execution."""
        mock_host = Mock()
        tool = TaskCreateTool(host_api=mock_host)
        result = tool.execute({"title": "Test task"}, dry_run=True)

        assert result.status == "ok"
        assert result.meta["dry_run"] is True

    def test_execute_missing_host_api(self):
        """Test execution without HostAPI."""
        tool = TaskCreateTool()
        result = tool.execute({"title": "Test task"}, dry_run=False)

        assert result.status == "error"
        assert "HostAPI not initialized" in result.error

    def test_execute_missing_title(self):
        """Test execution without required field."""
        mock_host = Mock()
        tool = TaskCreateTool(host_api=mock_host)

        result = tool.execute({}, dry_run=False)

        assert result.status == "error"
        assert "title is required" in result.error

    def test_execute_success(self):
        """Test successful task creation."""
        mock_host = Mock()
        mock_entity = Mock()
        mock_entity.id = "task-123"
        mock_entity.created_at = Mock()
        mock_entity.created_at.isoformat.return_value = "2025-10-08T12:00:00"

        mock_host.create_entity.return_value = mock_entity

        tool = TaskCreateTool(host_api=mock_host)
        result = tool.execute({"title": "Test task", "tags": ["test"]}, dry_run=False)

        assert result.status == "ok"
        assert result.data["uid"] == "task-123"
        assert result.data["title"] == "Test task"

        # Verify create_entity was called
        mock_host.create_entity.assert_called_once()


class TestTaskUpdateTool:
    """Tests for TaskUpdateTool."""

    def test_execute_success(self):
        """Test successful task update."""
        mock_host = Mock()
        mock_entity = Mock()
        mock_entity.id = "task-123"
        mock_entity.updated_at = Mock()
        mock_entity.updated_at.isoformat.return_value = "2025-10-08T12:00:00"

        mock_host.update_entity.return_value = mock_entity

        tool = TaskUpdateTool(host_api=mock_host)
        result = tool.execute({"uid": "task-123", "status": "done"}, dry_run=False)

        assert result.status == "ok"
        assert result.data["uid"] == "task-123"

    def test_execute_no_updates(self):
        """Test update with no fields."""
        mock_host = Mock()
        tool = TaskUpdateTool(host_api=mock_host)

        result = tool.execute({"uid": "task-123"}, dry_run=False)

        assert result.status == "error"
        assert "No updates provided" in result.error


class TestTaskGetTool:
    """Tests for TaskGetTool."""

    def test_execute_success(self):
        """Test successful task retrieval."""
        mock_host = Mock()
        mock_entity = Mock()
        mock_entity.id = "task-123"
        mock_entity.entity_type = "task"
        mock_entity.metadata = {"title": "Test"}
        mock_entity.created_at = Mock()
        mock_entity.created_at.isoformat.return_value = "2025-10-08T12:00:00"
        mock_entity.updated_at = Mock()
        mock_entity.updated_at.isoformat.return_value = "2025-10-08T12:00:00"

        mock_host.get_entity.return_value = mock_entity

        tool = TaskGetTool(host_api=mock_host)
        result = tool.execute({"uid": "task-123"}, dry_run=False)

        assert result.status == "ok"
        assert result.data["uid"] == "task-123"

    def test_execute_not_found(self):
        """Test task not found."""
        mock_host = Mock()
        mock_host.get_entity.return_value = None

        tool = TaskGetTool(host_api=mock_host)
        result = tool.execute({"uid": "nonexistent"}, dry_run=False)

        assert result.status == "error"
        assert "not found" in result.error


class TestTaskListTool:
    """Tests for TaskListTool."""

    def test_execute_all_tasks(self):
        """Test listing all tasks."""
        mock_host = Mock()
        mock_entity1 = Mock()
        mock_entity1.id = "task-1"
        mock_entity1.metadata = {"title": "Task 1", "status": "todo", "tags": []}
        mock_entity1.created_at = Mock()
        mock_entity1.created_at.isoformat.return_value = "2025-10-08T12:00:00"

        mock_host.list_entities.return_value = [mock_entity1]

        tool = TaskListTool(host_api=mock_host)
        result = tool.execute({}, dry_run=False)

        assert result.status == "ok"
        assert result.data["count"] == 1
        assert len(result.data["tasks"]) == 1

    def test_execute_with_status_filter(self):
        """Test listing with status filter."""
        mock_host = Mock()
        mock_entity1 = Mock()
        mock_entity1.metadata = {"status": "todo", "tags": []}
        mock_entity1.created_at = Mock()
        mock_entity1.created_at.isoformat.return_value = "2025-10-08T12:00:00"

        mock_entity2 = Mock()
        mock_entity2.metadata = {"status": "done", "tags": []}

        mock_host.list_entities.return_value = [mock_entity1, mock_entity2]

        tool = TaskListTool(host_api=mock_host)
        result = tool.execute({"status": "todo"}, dry_run=False)

        assert result.status == "ok"
        assert result.data["count"] == 1


class TestRollupDailyTool:
    """Tests for RollupDailyTool."""

    def test_get_parameters(self):
        """Test parameter schema."""
        tool = RollupDailyTool()
        params = tool.get_parameters()

        assert "date_local" in params["required"]

    def test_execute_dry_run(self):
        """Test dry run execution."""
        tool = RollupDailyTool(vault_path=Path("/tmp/vault"))
        result = tool.execute({"date_local": "2025-10-08"}, dry_run=True)

        assert result.status == "ok"
        assert result.meta["dry_run"] is True

    def test_execute_missing_vault_path(self):
        """Test execution without vault path."""
        tool = RollupDailyTool()
        result = tool.execute({"date_local": "2025-10-08"}, dry_run=False)

        assert result.status == "error"
        assert "Vault path not configured" in result.error

    def test_execute_success(self, tmp_path):
        """Test successful rollup generation."""
        tool = RollupDailyTool(vault_path=tmp_path)
        result = tool.execute({"date_local": "2025-10-08"}, dry_run=False)

        if result.status != "ok":
            print(f"Error: {result.error}")

        assert result.status == "ok", f"Expected ok but got error: {result.error}"
        assert "path" in result.data

        # Verify file was created
        rollup_path = tmp_path / "rollups" / "2025-10-08.md"
        assert rollup_path.exists()
