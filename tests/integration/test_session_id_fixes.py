"""Integration tests for session ID and response fixes.

Tests the critical fixes implemented for:
- Issue #1: Dual Executor Architecture (unified response interface)
- Issue #2: Session ID Confusion (standardized memory management)
"""

from pathlib import Path

import pytest

from src.kira.adapters.llm import AnthropicAdapter
from src.kira.agent.config import AgentConfig
from src.kira.agent.executor import AgentExecutor, ExecutionResult
from src.kira.agent.kira_tools import TaskCreateTool, TaskListTool
from src.kira.agent.tools import ToolRegistry
from src.kira.agent.unified_executor import ExecutorType, UnifiedExecutor
from src.kira.core.host import create_host_api


@pytest.fixture
def temp_vault(tmp_path):
    """Create temporary vault for testing."""
    vault_path = tmp_path / "test_vault"
    vault_path.mkdir()
    (vault_path / "tasks").mkdir()
    (vault_path / "notes").mkdir()
    return vault_path


@pytest.fixture
def host_api(temp_vault):
    """Create HostAPI for testing."""
    return create_host_api(temp_vault)


@pytest.fixture
def tool_registry(host_api):
    """Create tool registry with basic tools."""
    registry = ToolRegistry()
    registry.register(TaskCreateTool(host_api=host_api))
    registry.register(TaskListTool(host_api=host_api))
    return registry


@pytest.fixture
def agent_config():
    """Create agent config for testing."""
    return AgentConfig(
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        max_tool_calls=5,
        temperature=0.7,
    )


class TestExecutorResponseFields:
    """Test that both executors return .response field."""

    def test_legacy_executor_has_response_field(self, tool_registry, agent_config):
        """Test that legacy AgentExecutor returns .response field."""
        # Skip if no API key
        if not agent_config.anthropic_api_key or agent_config.anthropic_api_key == "test-key":
            pytest.skip("No API key configured")

        llm_adapter = AnthropicAdapter(api_key=agent_config.anthropic_api_key)
        executor = AgentExecutor(llm_adapter, tool_registry, agent_config)

        # Execute a simple request
        result = executor.chat_and_execute(
            "List tasks",
            session_id="test:session1"
        )

        # Verify result has .response field
        assert hasattr(result, "response"), "ExecutionResult should have .response field"
        assert isinstance(result.response, str), ".response should be a string"
        assert len(result.response) > 0, ".response should not be empty"

    def test_execution_result_dataclass_has_response(self):
        """Test that ExecutionResult dataclass has .response field."""
        result = ExecutionResult(
            status="ok",
            results=[{"status": "ok", "data": {"test": "data"}}],
            response="Test response"
        )

        assert result.response == "Test response"
        assert "response" in result.to_dict()


class TestSessionIDManagement:
    """Test session ID handling across executors."""

    def test_unified_executor_generates_default_session_id(self, tool_registry, agent_config):
        """Test that UnifiedExecutor generates session_id if not provided."""
        # Create mock executor
        class MockExecutor:
            def chat_and_execute(self, request, *, trace_id=None, session_id=None):
                # Verify session_id is provided
                assert session_id is not None, "session_id should be provided"
                assert session_id.startswith("default:"), "Default session_id should start with 'default:'"
                return ExecutionResult(status="ok", response="Test response")

        unified = UnifiedExecutor(MockExecutor(), ExecutorType.LEGACY)

        # Call without session_id
        result = unified.chat_and_execute("test request")

        # Should succeed (session_id was generated internally)
        assert result.status == "ok"

    def test_session_id_preserved_across_turns(self, tool_registry, agent_config):
        """Test that session_id preserves conversation context."""
        if not agent_config.anthropic_api_key or agent_config.anthropic_api_key == "test-key":
            pytest.skip("No API key configured")

        llm_adapter = AnthropicAdapter(api_key=agent_config.anthropic_api_key)
        executor = AgentExecutor(llm_adapter, tool_registry, agent_config)

        session_id = "test:conversation1"

        # First turn
        result1 = executor.chat_and_execute(
            "List tasks",
            session_id=session_id
        )

        # Verify memory was saved
        assert executor.memory.has_context(session_id)

        # Second turn - should have context from first turn
        result2 = executor.chat_and_execute(
            "How many tasks are there?",
            session_id=session_id
        )

        # Memory should have both turns
        context = executor.memory.get_context_messages(session_id)
        assert len(context) >= 2, "Should have at least 2 messages in context"


class TestMessageHandlerSimplification:
    """Test that MessageHandler correctly uses .response field."""

    def test_message_handler_uses_response_field(self):
        """Test that MessageHandler prefers .response over manual formatting."""
        from src.kira.agent.message_handler import MessageHandler

        # Create mock executor that returns .response
        class MockExecutor:
            def chat_and_execute(self, request, *, trace_id=None, session_id=None):
                return ExecutionResult(
                    status="ok",
                    results=[{"status": "ok", "data": {"count": 5}}],
                    response="Found 5 tasks"  # Natural language response
                )

        handler = MessageHandler(MockExecutor())

        # Format response
        response_text = handler._format_response(
            MockExecutor().chat_and_execute("test")
        )

        # Should use .response field directly
        assert response_text == "Found 5 tasks"


class TestTelegramGatewaySessionID:
    """Test that TelegramGateway passes session_id correctly."""

    def test_telegram_gateway_creates_consistent_session_id(self):
        """Test that TelegramGateway creates consistent session_id format."""
        from src.kira.agent.telegram_gateway import TelegramGateway

        # Create mock executor to capture session_id
        captured_session_id = None

        class MockExecutor:
            def chat_and_execute(self, request, *, trace_id=None, session_id=None):
                nonlocal captured_session_id
                captured_session_id = session_id
                return ExecutionResult(status="ok", response="Test")

        gateway = TelegramGateway(MockExecutor(), "test-token")

        # Process message
        message = {
            "text": "test message",
            "chat": {"id": 12345}
        }

        gateway.process_message(message)

        # Verify session_id format
        assert captured_session_id == "telegram:12345"


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_legacy_executor_works_with_trace_id_only(self, tool_registry, agent_config):
        """Test that legacy executor still works with only trace_id."""
        if not agent_config.anthropic_api_key or agent_config.anthropic_api_key == "test-key":
            pytest.skip("No API key configured")

        llm_adapter = AnthropicAdapter(api_key=agent_config.anthropic_api_key)
        executor = AgentExecutor(llm_adapter, tool_registry, agent_config)

        # Call with only trace_id (old behavior)
        result = executor.chat_and_execute(
            "List tasks",
            trace_id="test-trace-123"
        )

        # Should still work and have .response
        assert result.status in ["ok", "error"]
        assert hasattr(result, "response")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

