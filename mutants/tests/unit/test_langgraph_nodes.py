"""Unit tests for LangGraph nodes."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from kira.adapters.llm import LLMResponse, Message
from kira.agent.nodes import plan_node, reflect_node, route_node, tool_node, verify_node
from kira.agent.state import AgentState, Budget, ContextFlags
from kira.agent.tools import ToolResult


class MockLLMAdapter:
    """Mock LLM adapter for testing."""

    def __init__(self, response_content: str = ""):
        self.response_content = response_content
        self.calls = []

    def chat(self, messages, temperature=0.7, max_tokens=1000, timeout=30.0):
        """Mock chat method."""
        self.calls.append({
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        })
        return LLMResponse(
            content=self.response_content,
            finish_reason="stop",
            usage={"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50},
            model="mock-model",
        )


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name: str, result: ToolResult):
        self.name = name
        self.description = f"Mock tool {name}"
        self.result = result
        self.calls = []

    def get_parameters(self):
        """Get tool parameters."""
        return {"type": "object", "properties": {}}

    def execute(self, args, dry_run=False):
        """Execute tool."""
        self.calls.append({"args": args, "dry_run": dry_run})
        return self.result


class MockToolRegistry:
    """Mock tool registry for testing."""

    def __init__(self):
        self.tools = {}

    def register(self, tool):
        """Register a tool."""
        self.tools[tool.name] = tool

    def get(self, name):
        """Get tool by name."""
        return self.tools.get(name)

    def list_tools(self):
        """List all tools."""
        return list(self.tools.values())

    def get_tools_description(self):
        """Get tools description."""
        return "\n".join(f"- {t.name}: {t.description}" for t in self.tools.values())


def test_plan_node_success():
    """Test plan node with successful planning."""
    llm_adapter = MockLLMAdapter(
        response_content="""{
            "plan": ["Create a task"],
            "tool_calls": [
                {"tool": "task_create", "args": {"title": "Test"}, "dry_run": true}
            ],
            "reasoning": "User wants to create a task"
        }"""
    )

    state = AgentState(
        trace_id="test-123",
        messages=[{"role": "user", "content": "Create a task named Test"}],
    )

    result = plan_node(state, llm_adapter, "- task_create: Create a task")

    assert result["status"] == "planned"
    assert len(result["plan"]) == 1
    assert result["plan"][0]["tool"] == "task_create"
    assert "reasoning" in result["memory"]


def test_plan_node_no_user_message():
    """Test plan node with no user message."""
    llm_adapter = MockLLMAdapter()
    state = AgentState(trace_id="test-123", messages=[])

    result = plan_node(state, llm_adapter, "")

    assert result["status"] == "error"
    assert "No user message" in result["error"]


def test_plan_node_invalid_json():
    """Test plan node with invalid JSON response."""
    llm_adapter = MockLLMAdapter(response_content="Not valid JSON")
    state = AgentState(
        trace_id="test-123",
        messages=[{"role": "user", "content": "Do something"}],
    )

    result = plan_node(state, llm_adapter, "")

    assert result["status"] == "error"
    assert "Invalid plan JSON" in result["error"]


def test_plan_node_updates_token_budget():
    """Test that plan node updates token budget."""
    llm_adapter = MockLLMAdapter(
        response_content='{"plan": [], "tool_calls": [], "reasoning": "test"}'
    )
    state = AgentState(
        trace_id="test-123",
        messages=[{"role": "user", "content": "Test"}],
    )

    initial_tokens = state.budget.tokens_used
    result = plan_node(state, llm_adapter, "")

    # The mock returns 100 total tokens
    assert state.budget.tokens_used == initial_tokens + 100


def test_reflect_node_safe_plan():
    """Test reflect node with safe plan."""
    llm_adapter = MockLLMAdapter(
        response_content="""{
            "safe": true,
            "concerns": [],
            "reasoning": "Plan looks good"
        }"""
    )

    state = AgentState(
        trace_id="test-123",
        plan=[{"tool": "task_list", "args": {}, "dry_run": False}],
    )

    result = reflect_node(state, llm_adapter)

    assert result["status"] == "reflected"
    assert "reflection" in result["memory"]


def test_reflect_node_unsafe_plan_with_revision():
    """Test reflect node with unsafe plan that gets revised."""
    llm_adapter = MockLLMAdapter(
        response_content="""{
            "safe": false,
            "concerns": ["No dry_run on mutating operation"],
            "revised_plan": [
                {"tool": "task_create", "args": {"title": "Test"}, "dry_run": true}
            ],
            "reasoning": "Added dry_run flag"
        }"""
    )

    state = AgentState(
        trace_id="test-123",
        plan=[{"tool": "task_create", "args": {"title": "Test"}, "dry_run": False}],
    )

    result = reflect_node(state, llm_adapter)

    assert result["status"] == "reflected"
    assert "plan" in result
    assert result["plan"][0]["dry_run"] is True


def test_reflect_node_no_plan():
    """Test reflect node with no plan."""
    llm_adapter = MockLLMAdapter()
    state = AgentState(trace_id="test-123", plan=[])

    result = reflect_node(state, llm_adapter)

    assert result["status"] == "reflected"
    assert len(llm_adapter.calls) == 0


def test_tool_node_success():
    """Test tool node with successful execution."""
    tool = MockTool("task_create", ToolResult.ok({"id": "task-1", "title": "Test"}))
    registry = MockToolRegistry()
    registry.register(tool)

    state = AgentState(
        trace_id="test-123",
        plan=[{"tool": "task_create", "args": {"title": "Test"}, "dry_run": False}],
        current_step=0,
    )

    result = tool_node(state, registry)

    assert result["status"] == "executed"
    assert len(result["tool_results"]) == 1
    assert result["tool_results"][0]["status"] == "ok"
    assert result["current_step"] == 1
    assert len(tool.calls) == 1


def test_tool_node_tool_not_found():
    """Test tool node with unknown tool."""
    registry = MockToolRegistry()
    state = AgentState(
        trace_id="test-123",
        plan=[{"tool": "unknown_tool", "args": {}, "dry_run": False}],
        current_step=0,
    )

    result = tool_node(state, registry)

    assert result["status"] == "error"
    assert "Tool not found" in result["error"]


def test_tool_node_respects_dry_run():
    """Test tool node respects dry_run flag."""
    tool = MockTool("task_create", ToolResult.ok({"dry_run": True}))
    registry = MockToolRegistry()
    registry.register(tool)

    state = AgentState(
        trace_id="test-123",
        plan=[{"tool": "task_create", "args": {"title": "Test"}, "dry_run": True}],
        current_step=0,
    )

    result = tool_node(state, registry)

    assert result["status"] == "executed"
    assert tool.calls[0]["dry_run"] is True


def test_tool_node_global_dry_run():
    """Test tool node respects global dry_run flag."""
    tool = MockTool("task_create", ToolResult.ok({}))
    registry = MockToolRegistry()
    registry.register(tool)

    state = AgentState(
        trace_id="test-123",
        plan=[{"tool": "task_create", "args": {"title": "Test"}, "dry_run": False}],
        current_step=0,
        flags=ContextFlags(dry_run=True),
    )

    result = tool_node(state, registry)

    assert tool.calls[0]["dry_run"] is True


def test_tool_node_updates_budget():
    """Test tool node updates step and time budget."""
    tool = MockTool("task_create", ToolResult.ok({}))
    registry = MockToolRegistry()
    registry.register(tool)

    state = AgentState(
        trace_id="test-123",
        plan=[{"tool": "task_create", "args": {}, "dry_run": False}],
        current_step=0,
    )

    initial_steps = state.budget.steps_used
    initial_time = state.budget.wall_time_used

    result = tool_node(state, registry)

    assert state.budget.steps_used == initial_steps + 1
    assert state.budget.wall_time_used > initial_time


def test_tool_node_no_more_steps():
    """Test tool node when no more steps to execute."""
    registry = MockToolRegistry()
    state = AgentState(
        trace_id="test-123",
        plan=[{"tool": "task_create", "args": {}}],
        current_step=1,  # Already past the last step
    )

    result = tool_node(state, registry)

    assert result["status"] == "completed"


def test_verify_node_success():
    """Test verify node with successful results."""
    registry = MockToolRegistry()
    state = AgentState(
        trace_id="test-123",
        tool_results=[{"status": "ok", "data": {"id": "task-1"}}],
    )

    result = verify_node(state, registry)

    assert result["status"] == "verified"


def test_verify_node_no_results():
    """Test verify node with no results."""
    registry = MockToolRegistry()
    state = AgentState(trace_id="test-123", tool_results=[])

    result = verify_node(state, registry)

    assert result["status"] == "verified"


def test_verify_node_with_error():
    """Test verify node with error result."""
    registry = MockToolRegistry()
    state = AgentState(
        trace_id="test-123",
        tool_results=[{"status": "error", "error": "Something failed"}],
    )

    result = verify_node(state, registry)

    # Verification is skipped for errors
    assert result["status"] == "verified"


def test_route_node_budget_exceeded():
    """Test route node when budget is exceeded."""
    state = AgentState(trace_id="test-123")
    state.budget.steps_used = state.budget.max_steps

    next_node = route_node(state)

    assert next_node == "halt"


def test_route_node_error_with_retries():
    """Test route node with error and retries available."""
    state = AgentState(trace_id="test-123", error="Test error", retry_count=0)

    next_node = route_node(state)

    assert next_node == "plan"


def test_route_node_error_max_retries():
    """Test route node with error and max retries reached."""
    state = AgentState(trace_id="test-123", error="Test error", retry_count=2)

    next_node = route_node(state)

    assert next_node == "halt"


def test_route_node_pending_to_plan():
    """Test route node from pending to plan."""
    state = AgentState(trace_id="test-123", status="pending")

    next_node = route_node(state)

    assert next_node == "plan"


def test_route_node_planned_to_reflect():
    """Test route node from planned to reflect."""
    state = AgentState(
        trace_id="test-123",
        status="planned",
        flags=ContextFlags(enable_reflection=True),
    )

    next_node = route_node(state)

    assert next_node == "reflect"


def test_route_node_planned_skip_reflection():
    """Test route node from planned to tool (skip reflection)."""
    state = AgentState(
        trace_id="test-123",
        status="planned",
        flags=ContextFlags(enable_reflection=False),
    )

    next_node = route_node(state)

    assert next_node == "tool"


def test_route_node_reflected_to_tool():
    """Test route node from reflected to tool."""
    state = AgentState(trace_id="test-123", status="reflected")

    next_node = route_node(state)

    assert next_node == "tool"


def test_route_node_executed_to_verify():
    """Test route node from executed to verify."""
    state = AgentState(
        trace_id="test-123",
        status="executed",
        plan=[{"tool": "task_create"}],
        current_step=1,
        flags=ContextFlags(enable_verification=True),
    )

    next_node = route_node(state)

    assert next_node == "verify"


def test_route_node_executed_skip_verification():
    """Test route node from executed to done (skip verification)."""
    state = AgentState(
        trace_id="test-123",
        status="executed",
        plan=[{"tool": "task_create"}],
        current_step=1,
        flags=ContextFlags(enable_verification=False),
    )

    next_node = route_node(state)

    assert next_node == "done"


def test_route_node_executed_more_steps():
    """Test route node from executed to tool (more steps remain)."""
    state = AgentState(
        trace_id="test-123",
        status="executed",
        plan=[{"tool": "task_create"}, {"tool": "task_update"}],
        current_step=1,
        flags=ContextFlags(enable_verification=False),
    )

    next_node = route_node(state)

    assert next_node == "tool"


def test_route_node_verified_to_done():
    """Test route node from verified to respond (generates NL response)."""
    state = AgentState(
        trace_id="test-123",
        status="verified",
        plan=[{"tool": "task_create"}],
        current_step=1,
    )

    next_node = route_node(state)

    assert next_node == "respond"  # Changed to respond for NL response generation


def test_route_node_verified_more_steps():
    """Test route node from verified to tool (more steps remain)."""
    state = AgentState(
        trace_id="test-123",
        status="verified",
        plan=[{"tool": "task_create"}, {"tool": "task_update"}],
        current_step=1,
    )

    next_node = route_node(state)

    assert next_node == "tool"


def test_route_node_completed():
    """Test route node from completed to respond (generates NL response)."""
    state = AgentState(trace_id="test-123", status="completed")

    next_node = route_node(state)

    assert next_node == "respond"  # Changed to respond for NL response generation

