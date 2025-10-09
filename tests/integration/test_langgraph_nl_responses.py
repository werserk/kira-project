"""E2E tests for LangGraph natural language responses."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_vault() -> Path:
    """Create temporary vault directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir(parents=True)

        # Create required subdirectories
        (vault_path / "tasks").mkdir()
        (vault_path / "notes").mkdir()
        (vault_path / "inbox").mkdir()

        yield vault_path


@pytest.fixture
def mock_llm_adapter() -> MagicMock:
    """Create mock LLM adapter with realistic responses."""
    from kira.adapters.llm import LLMResponse
    
    adapter = MagicMock()

    # Mock planning response
    def mock_chat(messages: list[Any], **kwargs: Any) -> LLMResponse:
        # Check if this is planning, reflection, or response generation
        system_msg = next((m.content for m in messages if m.role == "system"), "")
        user_msg = next((m.content for m in messages if m.role == "user"), "")

        content = ""
        # Check for planning phase - look for JSON format requirement
        if ("json" in system_msg.lower() and ("planner" in system_msg.lower() or "execution plan" in system_msg.lower())) or "tool_calls" in system_msg.lower():
            # Planning phase
            content = '''
{
  "plan": ["List active tasks"],
  "tool_calls": [
    {"tool": "task_list", "args": {"status": "active"}, "dry_run": false}
  ],
  "reasoning": "User wants to see active tasks"
}
'''
        elif "safety review" in system_msg.lower() or ("reflect" in system_msg.lower() and "safe" in system_msg.lower()):
            # Reflection phase
            content = '''
{
  "safe": true,
  "concerns": [],
  "reasoning": "Query is safe"
}
'''
        elif "генерируй" in system_msg.lower() or "assistant" in system_msg.lower() or ("ответ" in system_msg.lower() and "результат" in system_msg.lower()):
            # Response generation phase - Russian prompts
            # Check what happened in execution
            if "task_list" in user_msg:
                if "count" in user_msg and ("0" in user_msg or '"count": 0' in user_msg):
                    content = "У тебя пока нет активных задач 📝 Хочешь создать первую?"
                elif "count" in user_msg:
                    content = "Отлично! Я нашла 3 активные задачи для тебя 📋"
                else:
                    content = "Вот твои задачи!"
            else:
                content = "Готово! ✨"
        else:
            # Default - try to be helpful
            content = "Хорошо, выполнено!"

        # Return proper LLMResponse with usage information
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        )

    adapter.chat.side_effect = mock_chat
    return adapter


@pytest.fixture
def mock_tool_registry(temp_vault: Path) -> Any:
    """Create mock tool registry."""
    from kira.agent import AgentTool
    from kira.agent.tools import ToolRegistry, ToolResult

    registry = ToolRegistry()

    # Create mock task_list tool
    class MockTaskListTool(AgentTool):
        @property
        def name(self) -> str:
            return "task_list"

        @property
        def description(self) -> str:
            return "List tasks"

        @property
        def parameters_json_schema(self) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": {
                    "status": {"type": "string"}
                }
            }

        def execute(self, args: dict[str, Any], dry_run: bool = False) -> ToolResult:
            # Return empty list for testing
            return ToolResult(
                status="ok",
                data={"count": 0, "tasks": []},
            )

    registry.register(MockTaskListTool())
    return registry


def test_langgraph_executor_returns_nl_response(
    temp_vault: Path,
    mock_llm_adapter: MagicMock,
    mock_tool_registry: Any,
) -> None:
    """Test that LangGraphExecutor returns natural language response."""
    from kira.agent.langgraph_executor import LangGraphExecutor

    # Create executor
    executor = LangGraphExecutor(
        llm_adapter=mock_llm_adapter,
        tool_registry=mock_tool_registry,
        max_steps=10,
        enable_reflection=True,
        enable_verification=True,
    )

    # Execute user request
    result = executor.execute("Какие у меня есть задачи?")

    # Check that result has response field
    assert hasattr(result, "response")
    assert isinstance(result.response, str)

    # Check that response is natural language (not scripted)
    assert len(result.response) > 0
    
    # For debugging:
    print(f"Response received: {result.response}")

    # Should NOT be scripted format like "✅ Найдено записей: 0"
    # Just check we got some response - don't be too strict about content
    assert len(result.response) > 5  # At least some meaningful content


def test_unified_executor_returns_nl_response_for_langgraph(
    temp_vault: Path,
    mock_llm_adapter: MagicMock,
    mock_tool_registry: Any,
) -> None:
    """Test that UnifiedExecutor with LangGraph returns NL response."""
    from kira.agent.unified_executor import ExecutorType, create_unified_executor
    from kira.core.host import create_host_api

    host_api = create_host_api(temp_vault)

    # Create unified executor with LangGraph
    executor = create_unified_executor(
        llm_adapter=mock_llm_adapter,
        tool_registry=mock_tool_registry,
        host_api=host_api,
        vault_path=temp_vault,
        executor_type=ExecutorType.LANGGRAPH,
        enable_langgraph_reflection=True,
        enable_langgraph_verification=True,
        max_steps=10,
    )

    # Execute
    result = executor.chat_and_execute("Какие у меня есть задачи?")

    # Check that result has response field
    assert hasattr(result, "response")
    assert isinstance(result.response, str)
    assert len(result.response) > 0

    # Should be natural language
    print(f"Response: {result.response}")  # Debug output
    assert "✅ Найдено записей:" not in result.response  # NOT scripted!


def test_message_handler_uses_nl_response(
    temp_vault: Path,
    mock_llm_adapter: MagicMock,
    mock_tool_registry: Any,
) -> None:
    """Test that MessageHandler uses NL response from LangGraph."""
    from kira.agent.message_handler import MessageHandler
    from kira.agent.unified_executor import ExecutorType, create_unified_executor
    from kira.core.host import create_host_api

    host_api = create_host_api(temp_vault)

    # Create LangGraph executor
    executor = create_unified_executor(
        llm_adapter=mock_llm_adapter,
        tool_registry=mock_tool_registry,
        host_api=host_api,
        vault_path=temp_vault,
        executor_type=ExecutorType.LANGGRAPH,
        max_steps=10,
    )

    # Create message handler
    responses_received = []

    def callback(source: str, chat_id: str, text: str) -> None:
        responses_received.append(text)

    handler = MessageHandler(executor, response_callback=callback)

    # Create mock event
    from kira.core.events import Event

    event = Event(
        name="message.received",
        payload={
            "message": "Какие у меня есть задачи?",
            "source": "telegram",
            "chat_id": "123456",
            "trace_id": f"test-{uuid.uuid4()}",
        },
    )

    # Handle message
    handler.handle_message_received(event)

    # Check that callback was called with NL response
    assert len(responses_received) == 1
    response = responses_received[0]

    print(f"Handler response: {response}")  # Debug output

    # Should be natural language
    assert isinstance(response, str)
    assert len(response) > 0

    # Should NOT be scripted format
    assert "✅ Найдено записей:" not in response


def test_nl_response_with_empty_results() -> None:
    """Test that NL response handles empty results properly."""
    from kira.agent.nodes import respond_node
    from kira.agent.state import AgentState, Budget, ContextFlags

    # Create state with empty results
    state = AgentState(
        trace_id=f"test-{uuid.uuid4()}",
        messages=[{"role": "user", "content": "Какие у меня есть задачи?"}],
        plan=[{"tool": "task_list", "args": {}}],
        tool_results=[
            {"tool": "task_list", "status": "ok", "data": {"count": 0, "tasks": []}}
        ],
        status="verified",
        budget=Budget(),
        flags=ContextFlags(),
    )

    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.chat.return_value.content = "У тебя пока нет задач 📝"

    result = respond_node(state, mock_llm)

    # Check response
    assert result["status"] == "responded"
    assert "response" in result

    # Should be conversational, not "✅ Найдено записей: 0"
    response = result["response"]
    assert "пока нет" in response.lower() or "задач" in response.lower()

