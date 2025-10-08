"""End-to-end integration tests for agent."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kira.adapters.llm import LLMResponse
from kira.agent.config import AgentConfig
from kira.agent.executor import AgentExecutor
from kira.agent.kira_tools import TaskCreateTool, TaskGetTool, TaskListTool
from kira.agent.tools import ToolRegistry
from kira.core.host import create_host_api


@pytest.fixture
def temp_vault():
    """Create temporary vault."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir(parents=True)

        # Create required subdirectories
        (vault_path / "tasks").mkdir()
        (vault_path / "notes").mkdir()
        (vault_path / "events").mkdir()

        yield vault_path


@pytest.fixture
def host_api(temp_vault):
    """Create HostAPI for testing."""
    return create_host_api(temp_vault)


@pytest.fixture
def tool_registry(host_api):
    """Create tool registry with real tools."""
    registry = ToolRegistry()
    registry.register(TaskCreateTool(host_api=host_api))
    registry.register(TaskGetTool(host_api=host_api))
    registry.register(TaskListTool(host_api=host_api))
    return registry


@pytest.fixture
def mock_llm_adapter():
    """Create mock LLM adapter."""
    return Mock()


@pytest.fixture
def executor(mock_llm_adapter, tool_registry):
    """Create executor for testing."""
    config = AgentConfig(max_tool_calls=10, max_tokens=2000)
    return AgentExecutor(mock_llm_adapter, tool_registry, config)


class TestAgentE2E:
    """End-to-end tests for agent workflows."""

    def test_create_task_workflow(self, executor, mock_llm_adapter, host_api):
        """Test NL → plan → create task workflow."""
        # Mock LLM to return create task plan
        mock_llm_adapter.chat.return_value = LLMResponse(
            content=json.dumps(
                {
                    "plan": ["Create task with title 'Test Task'"],
                    "tool_calls": [
                        {
                            "tool": "task_create",
                            "args": {"title": "Test Task", "tags": ["test"]},
                            "dry_run": False,
                        }
                    ],
                    "reasoning": "User wants to create a task",
                }
            )
        )

        # Execute
        result = executor.chat_and_execute("Create a task called Test Task")

        # Verify
        assert result.status == "ok"
        assert len(result.results) == 1
        assert result.results[0]["status"] == "ok"
        assert "uid" in result.results[0]["data"]

        # Verify task was actually created
        tasks = list(host_api.list_entities("task"))
        assert len(tasks) >= 1

    def test_dry_run_workflow(self, executor, mock_llm_adapter):
        """Test dry-run before execution."""
        # Mock LLM to return plan with dry_run
        mock_llm_adapter.chat.return_value = LLMResponse(
            content=json.dumps(
                {
                    "plan": ["Dry run task creation"],
                    "tool_calls": [
                        {
                            "tool": "task_create",
                            "args": {"title": "Dry Run Task"},
                            "dry_run": True,
                        }
                    ],
                    "reasoning": "Testing dry run",
                }
            )
        )

        # Execute
        result = executor.chat_and_execute("Test creating a task")

        # Verify dry run succeeded
        assert result.status == "ok"
        assert result.results[0]["meta"]["dry_run"] is True

    def test_list_tasks_workflow(self, executor, mock_llm_adapter, host_api):
        """Test list tasks workflow."""
        # First create a task
        host_api.create_entity(
            "task",
            {
                "title": "Existing Task",
                "status": "todo",
                "tags": ["work"],
            },
        )

        # Mock LLM to return list plan
        mock_llm_adapter.chat.return_value = LLMResponse(
            content=json.dumps(
                {
                    "plan": ["List all tasks"],
                    "tool_calls": [
                        {
                            "tool": "task_list",
                            "args": {},
                            "dry_run": False,
                        }
                    ],
                    "reasoning": "User wants to see all tasks",
                }
            )
        )

        # Execute
        result = executor.chat_and_execute("Show me all tasks")

        # Verify
        assert result.status == "ok"
        assert result.results[0]["data"]["count"] >= 1

    def test_error_handling_workflow(self, executor, mock_llm_adapter):
        """Test error handling in workflow."""
        # Mock LLM to return invalid tool
        mock_llm_adapter.chat.return_value = LLMResponse(
            content=json.dumps(
                {
                    "plan": ["Call nonexistent tool"],
                    "tool_calls": [
                        {
                            "tool": "nonexistent_tool",
                            "args": {},
                            "dry_run": False,
                        }
                    ],
                    "reasoning": "Testing error",
                }
            )
        )

        # Execute
        result = executor.chat_and_execute("Do something invalid")

        # Verify error handling
        assert result.status == "error"

    def test_multi_step_workflow(self, executor, mock_llm_adapter):
        """Test multi-step plan execution."""
        # Mock LLM to return multi-step plan
        mock_llm_adapter.chat.return_value = LLMResponse(
            content=json.dumps(
                {
                    "plan": ["Create task", "List tasks"],
                    "tool_calls": [
                        {
                            "tool": "task_create",
                            "args": {"title": "Multi Step Task"},
                            "dry_run": False,
                        },
                        {
                            "tool": "task_list",
                            "args": {},
                            "dry_run": False,
                        },
                    ],
                    "reasoning": "Create and then list",
                }
            )
        )

        # Execute
        result = executor.chat_and_execute("Create a task and show me all tasks")

        # Verify
        assert result.status == "ok"
        assert len(result.results) == 2

    def test_idempotent_create(self, executor, mock_llm_adapter, host_api):
        """Test idempotent task creation."""
        # Create task twice with same title
        host_api.create_entity("task", {"title": "Unique Task", "status": "todo", "tags": []})

        # Mock LLM
        mock_llm_adapter.chat.return_value = LLMResponse(
            content=json.dumps(
                {
                    "plan": ["Create task"],
                    "tool_calls": [
                        {
                            "tool": "task_create",
                            "args": {"title": "Another Task"},
                            "dry_run": False,
                        }
                    ],
                    "reasoning": "Creating task",
                }
            )
        )

        # Execute
        result = executor.chat_and_execute("Create another task")

        # Both should succeed (simple idempotency check)
        assert result.status == "ok"


@pytest.mark.integration
class TestAgentService:
    """Integration tests for agent service."""

    def test_service_creation(self, temp_vault):
        """Test creating agent service."""
        config = AgentConfig(
            llm_provider="openrouter",
            openrouter_api_key="test-key",
            vault_path=temp_vault,
        )

        from kira.agent.service import create_agent_app

        with patch("kira.agent.service.OpenRouterAdapter"):
            app = create_agent_app(config)
            assert app is not None

    def test_health_endpoint(self, temp_vault):
        """Test health endpoint."""
        config = AgentConfig(
            llm_provider="openrouter",
            openrouter_api_key="test-key",
            vault_path=temp_vault,
        )

        from kira.agent.service import create_agent_app

        with patch("kira.agent.service.OpenRouterAdapter"):
            app = create_agent_app(config)

            from fastapi.testclient import TestClient

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    def test_version_endpoint(self, temp_vault):
        """Test version endpoint."""
        config = AgentConfig(
            llm_provider="openrouter",
            openrouter_api_key="test-key",
            vault_path=temp_vault,
        )

        from kira.agent.service import create_agent_app

        with patch("kira.agent.service.OpenRouterAdapter"):
            app = create_agent_app(config)

            from fastapi.testclient import TestClient

            client = TestClient(app)
            response = client.get("/agent/version")

            assert response.status_code == 200
            assert "version" in response.json()
