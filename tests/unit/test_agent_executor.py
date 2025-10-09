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

    def test_chat_and_execute_with_timeout(self):
        """Test chat and execute with LLM timeout.
        
        Real scenario: OpenRouter/Anthropic API takes >30 seconds to respond.
        System should catch timeout and return clear error.
        """
        # Mock LLM to raise timeout
        self.mock_llm.chat.side_effect = TimeoutError("The read operation timed out")

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        result = executor.chat_and_execute("Создай задачу: Проверить почту завтра в 10:00")

        assert result.status == "error"
        assert "timed out" in result.error.lower()

    def test_plan_with_wrong_tool_name(self):
        """Test when LLM returns wrong tool name.
        
        Bug scenario: LLM returns 'create_task' instead of 'task_create'.
        Should fail gracefully with clear error message.
        """
        # Mock LLM to return wrong tool name
        self.mock_llm.chat.return_value = LLMResponse(
            content="""
            {
                "plan": ["Create task"],
                "tool_calls": [
                    {"tool": "create_task", "args": {"title": "Test"}, "dry_run": false}
                ],
                "reasoning": "Creating task"
            }
            """
        )

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        result = executor.chat_and_execute("Create a test task")

        # Should complete but with error for missing tool
        assert result.status == "error"
        assert len(result.results) == 1
        assert "Tool not found" in result.results[0]["error"]
        assert "create_task" in result.results[0]["error"]

    def test_execute_with_rate_limit_error(self):
        """Test handling when LLM API returns rate limit error."""
        # Mock LLM to raise rate limit error (common with API keys)
        self.mock_llm.chat.side_effect = Exception("Rate limit exceeded. Please try again later.")

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        result = executor.chat_and_execute("Test query")

        assert result.status == "error"
        assert "Rate limit" in result.error

    def test_complex_user_query_with_date(self):
        """Test parsing complex user query with temporal information.
        
        Real query: 'Завтра мне нужно помыть полы. Поставь задачу'
        Should extract date and create task with due_ts.
        """
        # Mock successful LLM response with temporal parsing
        self.mock_llm.chat.return_value = LLMResponse(
            content="""
            {
                "plan": ["Parse 'завтра' as tomorrow's date", "Create task with due date"],
                "tool_calls": [
                    {
                        "tool": "task_create",
                        "args": {
                            "title": "Помыть полы",
                            "due_ts": "2025-10-10T00:00:00Z"
                        },
                        "dry_run": false
                    }
                ],
                "reasoning": "User wants to create task for tomorrow"
            }
            """
        )

        # Register mock tool
        mock_tool = Mock()
        mock_tool.name = "task_create"
        mock_tool.description = "Create task"
        mock_tool.get_parameters.return_value = {}
        mock_tool.execute.return_value = ToolResult.ok({
            "id": "task-20251010-0001",
            "title": "Помыть полы",
            "due_ts": "2025-10-10T00:00:00Z"
        })

        self.tool_registry.register(mock_tool)

        executor = AgentExecutor(self.mock_llm, self.tool_registry, self.config)

        result = executor.chat_and_execute("Завтра мне нужно помыть полы. Поставь задачу")

        assert result.status == "ok"
        assert len(result.results) == 1
        assert result.results[0]["data"]["title"] == "Помыть полы"
        assert "due_ts" in result.results[0]["data"]
