"""Unit tests for agent executor."""

from unittest.mock import Mock

import pytest

from kira.adapters.llm import LLMResponse, Message
from kira.agent.config import AgentConfig
from kira.agent.executor import AgentExecutor, ExecutionPlan, ExecutionStep
from kira.agent.tools import ToolRegistry, ToolResult


class TestExecutionPlan:
    """Tests for ExecutionPlan."""

    def test_creation(self):
        """Test plan creation."""
        steps = [
            ExecutionStep(tool="test_tool", args={"key": "value"}, dry_run=True)
        ]
        plan = ExecutionPlan(
            steps=steps,
            reasoning="Test reasoning",
            plan_description=["Step 1", "Step 2"],
        )

        assert len(plan.steps) == 1
        assert plan.reasoning == "Test reasoning"


class TestAgentExecutor:
    """Tests for AgentExecutor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.tool_registry = ToolRegistry()
        self.config = AgentConfig(max_tool_calls=5, max_tokens=1000)

    def test_init(self):
        """Test executor initialization."""
        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        assert executor.llm_adapter == self.mock_llm
        assert executor.tool_registry == self.tool_registry
        assert executor.config == self.config

    def test_parse_plan_success(self):
        """Test parsing valid LLM response."""
        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        llm_response = """
        {
            "plan": ["Create task", "Verify"],
            "tool_calls": [
                {"tool": "task_create", "args": {"title": "Test"}, "dry_run": true}
            ],
            "reasoning": "Need to create a task"
        }
        """

        plan = executor._parse_plan(llm_response)

        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "task_create"
        assert plan.steps[0].dry_run is True
        assert plan.reasoning == "Need to create a task"

    def test_parse_plan_invalid_json(self):
        """Test parsing invalid JSON."""
        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        with pytest.raises(ValueError, match="Failed to parse"):
            executor._parse_plan("not valid json")

    def test_execute_step_success(self):
        """Test successful step execution."""
        # Register mock tool
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.execute.return_value = ToolResult.ok({"result": "success"})

        self.tool_registry.register(mock_tool)

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        step = ExecutionStep(tool="test_tool", args={"key": "value"})
        result = executor.execute_step(step, trace_id="test-123")

        assert result.status == "ok"
        assert result.data["result"] == "success"
        assert result.meta["trace_id"] == "test-123"

    def test_execute_step_tool_not_found(self):
        """Test step execution with missing tool."""
        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        step = ExecutionStep(tool="nonexistent", args={})
        result = executor.execute_step(step, trace_id="test-123")

        assert result.status == "error"
        assert "Tool not found" in result.error

    def test_execute_plan_success(self):
        """Test successful plan execution."""
        # Register mock tool
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.execute.return_value = ToolResult.ok({"result": "success"})

        self.tool_registry.register(mock_tool)

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        plan = ExecutionPlan(
            steps=[
                ExecutionStep(tool="test_tool", args={"key": "value"}),
            ]
        )

        result = executor.execute_plan(plan, trace_id="test-123")

        assert result.status == "ok"
        assert len(result.results) == 1
        assert result.trace_id == "test-123"

    def test_execute_plan_with_error(self):
        """Test plan execution with error."""
        # Register mock tool that fails
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.execute.return_value = ToolResult.error("Tool failed")

        self.tool_registry.register(mock_tool)

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        plan = ExecutionPlan(
            steps=[
                ExecutionStep(tool="test_tool", args={}),
            ]
        )

        result = executor.execute_plan(plan)

        assert result.status == "error"
        assert len(result.results) == 1

    def test_chat_and_execute_success(self):
        """Test full chat and execute workflow."""
        # Mock LLM response
        self.mock_llm.chat.return_value = LLMResponse(
            content="""
            {
                "plan": ["Create task"],
                "tool_calls": [
                    {"tool": "test_tool", "args": {"title": "Test"}, "dry_run": false}
                ],
                "reasoning": "Creating task"
            }
            """
        )

        # Register mock tool
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_tool.get_parameters.return_value = {}
        mock_tool.execute.return_value = ToolResult.ok({"created": True})

        self.tool_registry.register(mock_tool)

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        result = executor.chat_and_execute("Create a test task")

        if result.status != "ok":
            print(f"Error: {result.error}")
            print(f"Results: {result.results}")

        assert result.status == "ok", f"Expected ok but got: {result.error}"
        assert len(result.results) > 0

    def test_chat_and_execute_with_exception(self):
        """Test chat and execute with exception."""
        # Mock LLM to raise exception
        self.mock_llm.chat.side_effect = Exception("LLM error")

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        result = executor.chat_and_execute("Test")

        assert result.status == "error"
        assert "LLM error" in result.error
