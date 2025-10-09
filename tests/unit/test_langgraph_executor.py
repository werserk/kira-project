"""Unit tests for LangGraph executor."""

from __future__ import annotations

import pytest

# Skip all tests in this file if LangGraph is not available
pytest.importorskip("langgraph")

from kira.adapters.llm import LLMResponse
from kira.agent.langgraph_executor import ExecutionResult, LangGraphExecutor
from kira.agent.state import AgentState, Budget
from kira.agent.tools import ToolResult


class MockLLMAdapter:
    """Mock LLM adapter for testing."""

    def __init__(self, plan_response: str):
        self.plan_response = plan_response
        self.calls = []

    def chat(self, messages, temperature=0.7, max_tokens=1000, timeout=30.0):
        """Mock chat method."""
        self.calls.append("chat")
        return LLMResponse(
            content=self.plan_response,
            finish_reason="stop",
            usage={"total_tokens": 100},
            model="mock",
        )


class MockTool:
    """Mock tool."""

    def __init__(self, name: str, result: ToolResult):
        self.name = name
        self.description = f"Mock {name}"
        self.result = result
        self.execution_count = 0

    def get_parameters(self):
        return {"type": "object", "properties": {}}

    def execute(self, args, dry_run=False):
        self.execution_count += 1
        return self.result


class MockToolRegistry:
    """Mock tool registry."""

    def __init__(self):
        self.tools = {}

    def register(self, tool):
        self.tools[tool.name] = tool

    def get(self, name):
        return self.tools.get(name)

    def list_tools(self):
        return list(self.tools.values())

    def get_tools_description(self):
        return "\n".join(f"- {t.name}: {t.description}" for t in self.tools.values())


def test_execution_result_success():
    """Test execution result for successful execution."""
    state = AgentState(trace_id="test-123", status="completed")
    result = ExecutionResult(state)

    assert result.success is True
    assert result.status == "completed"
    assert result.error is None


def test_execution_result_error():
    """Test execution result for failed execution."""
    state = AgentState(trace_id="test-123", status="error", error="Something failed")
    result = ExecutionResult(state)

    assert result.success is False
    assert result.status == "error"
    assert result.error == "Something failed"


def test_execution_result_to_dict():
    """Test execution result serialization."""
    state = AgentState(
        trace_id="test-123",
        status="completed",
        tool_results=[{"status": "ok", "data": {"id": "task-1"}}],
    )
    result = ExecutionResult(state)

    data = result.to_dict()

    assert data["trace_id"] == "test-123"
    assert data["status"] == "completed"
    assert data["success"] is True
    assert len(data["tool_results"]) == 1
    assert "budget" in data


def test_langgraph_executor_initialization():
    """Test LangGraph executor initialization."""
    llm_adapter = MockLLMAdapter("{}")
    tool_registry = MockToolRegistry()

    executor = LangGraphExecutor(
        llm_adapter,
        tool_registry,
        max_steps=5,
        max_tokens=5000,
    )

    assert executor.max_steps == 5
    assert executor.max_tokens == 5000
    assert executor.graph is not None


def test_langgraph_executor_execute_simple():
    """Test executor with simple plan."""
    plan_response = """{
        "plan": ["List tasks"],
        "tool_calls": [
            {"tool": "task_list", "args": {}, "dry_run": false}
        ],
        "reasoning": "User wants to list tasks"
    }"""

    llm_adapter = MockLLMAdapter(plan_response)
    tool_registry = MockToolRegistry()

    task_list_tool = MockTool("task_list", ToolResult.ok({"count": 0, "tasks": []}))
    tool_registry.register(task_list_tool)

    executor = LangGraphExecutor(
        llm_adapter,
        tool_registry,
        enable_reflection=False,
        enable_verification=False,
    )

    result = executor.execute("List all tasks")

    assert result.success is True
    assert task_list_tool.execution_count == 1
    assert len(result.tool_results) == 1


def test_langgraph_executor_dry_run():
    """Test executor with dry_run mode."""
    plan_response = """{
        "plan": ["Create task"],
        "tool_calls": [
            {"tool": "task_create", "args": {"title": "Test"}, "dry_run": false}
        ],
        "reasoning": "Create task"
    }"""

    llm_adapter = MockLLMAdapter(plan_response)
    tool_registry = MockToolRegistry()

    task_create_tool = MockTool("task_create", ToolResult.ok({"id": "task-1"}))
    tool_registry.register(task_create_tool)

    executor = LangGraphExecutor(
        llm_adapter,
        tool_registry,
        enable_reflection=False,
        enable_verification=False,
    )

    result = executor.execute("Create a task", dry_run=True)

    # Even though plan says dry_run=false, global dry_run should override
    assert result.success is True


def test_langgraph_executor_with_trace_id():
    """Test executor with custom trace ID."""
    plan_response = """{
        "plan": ["List tasks"],
        "tool_calls": [
            {"tool": "task_list", "args": {}, "dry_run": false}
        ],
        "reasoning": "List"
    }"""

    llm_adapter = MockLLMAdapter(plan_response)
    tool_registry = MockToolRegistry()
    tool_registry.register(MockTool("task_list", ToolResult.ok({})))

    executor = LangGraphExecutor(
        llm_adapter,
        tool_registry,
        enable_reflection=False,
        enable_verification=False,
    )

    result = executor.execute("List tasks", trace_id="custom-trace-123")

    assert result.trace_id == "custom-trace-123"


def test_langgraph_executor_budget_limits():
    """Test executor respects budget limits."""
    plan_response = """{
        "plan": ["Create many tasks"],
        "tool_calls": [
            {"tool": "task_create", "args": {"title": "Task 1"}, "dry_run": false},
            {"tool": "task_create", "args": {"title": "Task 2"}, "dry_run": false},
            {"tool": "task_create", "args": {"title": "Task 3"}, "dry_run": false},
            {"tool": "task_create", "args": {"title": "Task 4"}, "dry_run": false},
            {"tool": "task_create", "args": {"title": "Task 5"}, "dry_run": false}
        ],
        "reasoning": "Create multiple tasks"
    }"""

    llm_adapter = MockLLMAdapter(plan_response)
    tool_registry = MockToolRegistry()

    task_create_tool = MockTool("task_create", ToolResult.ok({}))
    tool_registry.register(task_create_tool)

    executor = LangGraphExecutor(
        llm_adapter,
        tool_registry,
        max_steps=3,  # Limit to 3 steps
        enable_reflection=False,
        enable_verification=False,
    )

    result = executor.execute("Create tasks")

    # Should stop at budget limit
    assert task_create_tool.execution_count <= 3


def test_langgraph_executor_get_graph_diagram():
    """Test getting graph visualization."""
    llm_adapter = MockLLMAdapter("{}")
    tool_registry = MockToolRegistry()

    executor = LangGraphExecutor(llm_adapter, tool_registry)

    diagram = executor.get_graph_diagram()

    # Should return some string representation
    assert isinstance(diagram, str)
    assert len(diagram) > 0


def test_langgraph_executor_tool_error():
    """Test executor handles tool errors gracefully."""
    plan_response = """{
        "plan": ["Create task"],
        "tool_calls": [
            {"tool": "task_create", "args": {"title": "Test"}, "dry_run": False}
        ],
        "reasoning": "Create"
    }"""

    llm_adapter = MockLLMAdapter(plan_response)
    tool_registry = MockToolRegistry()

    # Tool that returns error
    task_create_tool = MockTool("task_create", ToolResult.error("Validation failed"))
    tool_registry.register(task_create_tool)

    executor = LangGraphExecutor(
        llm_adapter,
        tool_registry,
        enable_reflection=False,
        enable_verification=False,
    )

    result = executor.execute("Create a task")

    assert result.success is False
    # Status should be "responded" since the executor generates a response even for errors
    assert result.status == "responded"


def test_langgraph_executor_streaming():
    """Test executor streaming mode."""
    plan_response = """{
        "plan": ["List tasks"],
        "tool_calls": [
            {"tool": "task_list", "args": {}, "dry_run": false}
        ],
        "reasoning": "List"
    }"""

    llm_adapter = MockLLMAdapter(plan_response)
    tool_registry = MockToolRegistry()
    tool_registry.register(MockTool("task_list", ToolResult.ok({})))

    executor = LangGraphExecutor(
        llm_adapter,
        tool_registry,
        enable_reflection=False,
        enable_verification=False,
    )

    steps = list(executor.stream("List tasks"))

    # Should have multiple steps
    assert len(steps) > 0

    # Each step should be (node_name, result)
    for node_name, result in steps:
        assert isinstance(node_name, str)
        assert isinstance(result, ExecutionResult)


def test_langgraph_executor_multi_step():
    """Test executor with multi-step plan."""
    plan_response = """{
        "plan": ["List tasks", "Create task"],
        "tool_calls": [
            {"tool": "task_list", "args": {}, "dry_run": false},
            {"tool": "task_create", "args": {"title": "New"}, "dry_run": false}
        ],
        "reasoning": "List then create"
    }"""

    llm_adapter = MockLLMAdapter(plan_response)
    tool_registry = MockToolRegistry()

    list_tool = MockTool("task_list", ToolResult.ok({"count": 0}))
    create_tool = MockTool("task_create", ToolResult.ok({"id": "task-1"}))

    tool_registry.register(list_tool)
    tool_registry.register(create_tool)

    executor = LangGraphExecutor(
        llm_adapter,
        tool_registry,
        enable_reflection=False,
        enable_verification=False,
    )

    result = executor.execute("List and create")

    assert result.success is True
    assert list_tool.execution_count == 1
    assert create_tool.execution_count == 1
    assert len(result.tool_results) == 2

