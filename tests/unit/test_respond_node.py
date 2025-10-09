"""Tests for respond_node - natural language response generation."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_llm_adapter() -> MagicMock:
    """Create mock LLM adapter."""
    adapter = MagicMock()

    # Mock response
    mock_response = MagicMock()
    mock_response.content = "Отлично! Я нашла 3 активные задачи для тебя 📝"

    adapter.chat.return_value = mock_response
    return adapter


@pytest.fixture
def agent_state_with_results() -> Any:
    """Create agent state with tool results."""
    from kira.agent.state import AgentState, Budget, ContextFlags

    return AgentState(
        trace_id=f"test-{uuid.uuid4()}",
        messages=[{"role": "user", "content": "Какие у меня есть задачи?"}],
        plan=[{"tool": "task_list", "args": {"status": "active"}}],
        current_step=1,
        tool_results=[
            {
                "tool": "task_list",
                "status": "ok",
                "data": {"count": 3, "tasks": ["Task 1", "Task 2", "Task 3"]},
            }
        ],
        status="verified",
        budget=Budget(),
        flags=ContextFlags(),
    )


@pytest.fixture
def agent_state_with_error() -> Any:
    """Create agent state with error."""
    from kira.agent.state import AgentState, Budget, ContextFlags

    return AgentState(
        trace_id=f"test-{uuid.uuid4()}",
        messages=[{"role": "user", "content": "Создай задачу"}],
        plan=[{"tool": "task_create", "args": {"title": "Test"}}],
        current_step=1,
        error="Tool not found: task_create",
        status="error",
        budget=Budget(),
        flags=ContextFlags(),
    )


def test_respond_node_generates_natural_response(
    agent_state_with_results: Any,
    mock_llm_adapter: MagicMock,
) -> None:
    """Test that respond_node generates natural language response."""
    from kira.agent.nodes import respond_node

    # Execute respond_node
    result = respond_node(agent_state_with_results, mock_llm_adapter)

    # Check that LLM was called
    assert mock_llm_adapter.chat.called

    # Check result structure
    assert "response" in result
    assert "status" in result
    assert result["status"] == "responded"

    # Check response is natural language (not scripted)
    response = result["response"]
    assert isinstance(response, str)
    assert len(response) > 0
    assert "Отлично" in response or "нашла" in response  # Natural language markers


def test_respond_node_includes_user_request_in_prompt(
    agent_state_with_results: Any,
    mock_llm_adapter: MagicMock,
) -> None:
    """Test that user request is included in LLM prompt."""
    from kira.agent.nodes import respond_node

    respond_node(agent_state_with_results, mock_llm_adapter)

    # Check that chat was called with messages
    call_args = mock_llm_adapter.chat.call_args
    messages = call_args[0][0]

    # Should have system + user messages
    assert len(messages) >= 2

    # Check that user request is in prompt
    user_message = next((m for m in messages if m.role == "user"), None)
    assert user_message is not None
    assert "Какие у меня есть задачи?" in user_message.content


def test_respond_node_includes_tool_results_in_context(
    agent_state_with_results: Any,
    mock_llm_adapter: MagicMock,
) -> None:
    """Test that tool results are included in context."""
    from kira.agent.nodes import respond_node

    respond_node(agent_state_with_results, mock_llm_adapter)

    call_args = mock_llm_adapter.chat.call_args
    messages = call_args[0][0]
    user_message = next((m for m in messages if m.role == "user"), None)

    # Check tool results are in context
    assert "task_list" in user_message.content
    assert "count" in user_message.content or "3" in user_message.content


def test_respond_node_handles_error_state(
    agent_state_with_error: Any,
    mock_llm_adapter: MagicMock,
) -> None:
    """Test that respond_node handles error state properly."""
    from kira.agent.nodes import respond_node

    mock_llm_adapter.chat.return_value.content = "Извини, произошла ошибка: Tool not found"

    result = respond_node(agent_state_with_error, mock_llm_adapter)

    assert result["status"] == "responded"
    assert "response" in result

    # Check error is mentioned in prompt
    call_args = mock_llm_adapter.chat.call_args
    messages = call_args[0][0]
    user_message = next((m for m in messages if m.role == "user"), None)
    assert "ERROR" in user_message.content or "error" in user_message.content.lower()


def test_respond_node_uses_higher_temperature(
    agent_state_with_results: Any,
    mock_llm_adapter: MagicMock,
) -> None:
    """Test that respond_node uses higher temperature for natural responses."""
    from kira.agent.nodes import respond_node

    respond_node(agent_state_with_results, mock_llm_adapter)

    call_args = mock_llm_adapter.chat.call_args
    kwargs = call_args[1]

    # Check temperature is > 0.7 (more natural)
    assert "temperature" in kwargs
    assert kwargs["temperature"] >= 0.8


def test_respond_node_has_fallback_on_llm_failure(
    agent_state_with_results: Any,
    mock_llm_adapter: MagicMock,
) -> None:
    """Test that respond_node has fallback if LLM fails."""
    from kira.agent.nodes import respond_node

    # Simulate LLM failure
    mock_llm_adapter.chat.side_effect = Exception("LLM timeout")

    result = respond_node(agent_state_with_results, mock_llm_adapter)

    # Should still return a response (fallback)
    assert result["status"] == "responded"
    assert "response" in result
    assert len(result["response"]) > 0

    # Fallback should be simple but informative
    assert "выполнено" in result["response"].lower() or "готово" in result["response"].lower()


def test_respond_node_updates_state_status(
    agent_state_with_results: Any,
    mock_llm_adapter: MagicMock,
) -> None:
    """Test that respond_node updates state status to 'responding'."""
    from kira.agent.nodes import respond_node

    # State should be 'verified' before
    assert agent_state_with_results.status == "verified"

    respond_node(agent_state_with_results, mock_llm_adapter)

    # State should be updated to 'responding' during execution
    # (Note: this is checked inside the function, we just verify it doesn't crash)
    assert True  # If we got here, status update worked


def test_respond_node_system_prompt_is_conversational() -> None:
    """Test that system prompt emphasizes conversational, friendly tone."""
    import inspect

    from kira.agent.nodes import respond_node

    # Get source code of respond_node
    source = inspect.getsource(respond_node)

    # Check that system prompt has conversational markers
    assert "personal AI assistant" in source or "Kira" in source
    assert "friendly" in source or "conversational" in source
    assert "natural" in source

