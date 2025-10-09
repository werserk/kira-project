"""Unit tests for LangGraph agent state."""

from __future__ import annotations

import pytest

from kira.agent.state import AgentState, Budget, ContextFlags


def test_budget_creation():
    """Test budget creation and defaults."""
    budget = Budget()
    assert budget.max_steps == 10
    assert budget.max_tokens == 10000
    assert budget.max_wall_time_seconds == 300.0
    assert budget.steps_used == 0
    assert budget.tokens_used == 0
    assert budget.wall_time_used == 0.0


def test_budget_exceeded_steps():
    """Test budget exceeded detection for steps."""
    budget = Budget(max_steps=5)
    assert not budget.is_exceeded()

    budget.steps_used = 5
    assert budget.is_exceeded()


def test_budget_exceeded_tokens():
    """Test budget exceeded detection for tokens."""
    budget = Budget(max_tokens=1000)
    assert not budget.is_exceeded()

    budget.tokens_used = 1000
    assert budget.is_exceeded()


def test_budget_exceeded_time():
    """Test budget exceeded detection for wall time."""
    budget = Budget(max_wall_time_seconds=60.0)
    assert not budget.is_exceeded()

    budget.wall_time_used = 60.0
    assert budget.is_exceeded()


def test_budget_to_dict():
    """Test budget serialization."""
    budget = Budget(max_steps=5, steps_used=2)
    data = budget.to_dict()

    assert data["max_steps"] == 5
    assert data["steps_used"] == 2
    assert "max_tokens" in data
    assert "max_wall_time_seconds" in data


def test_context_flags_defaults():
    """Test context flags defaults."""
    flags = ContextFlags()
    assert flags.dry_run is False
    assert flags.require_confirmation is False
    assert flags.enable_reflection is True
    assert flags.enable_verification is True


def test_context_flags_to_dict():
    """Test context flags serialization."""
    flags = ContextFlags(dry_run=True, enable_reflection=False)
    data = flags.to_dict()

    assert data["dry_run"] is True
    assert data["enable_reflection"] is False
    assert data["require_confirmation"] is False


def test_agent_state_creation():
    """Test agent state creation."""
    state = AgentState(trace_id="test-123", user="alice")

    assert state.trace_id == "test-123"
    assert state.user == "alice"
    assert state.session_id == ""
    assert state.messages == []
    assert state.plan == []
    assert state.current_step == 0
    assert state.status == "pending"


def test_agent_state_with_messages():
    """Test agent state with messages."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    state = AgentState(trace_id="test-123", messages=messages)

    assert len(state.messages) == 2
    assert state.messages[0]["role"] == "user"


def test_agent_state_with_plan():
    """Test agent state with execution plan."""
    plan = [
        {"tool": "task_create", "args": {"title": "Test"}, "dry_run": True},
    ]
    state = AgentState(trace_id="test-123", plan=plan)

    assert len(state.plan) == 1
    assert state.plan[0]["tool"] == "task_create"


def test_agent_state_to_dict():
    """Test agent state serialization."""
    state = AgentState(
        trace_id="test-123",
        user="alice",
        messages=[{"role": "user", "content": "Hello"}],
    )

    data = state.to_dict()

    assert data["trace_id"] == "test-123"
    assert data["user"] == "alice"
    assert len(data["messages"]) == 1
    assert "budget" in data
    assert "flags" in data
    assert data["status"] == "pending"


def test_agent_state_from_dict():
    """Test agent state deserialization."""
    data = {
        "trace_id": "test-456",
        "user": "bob",
        "messages": [{"role": "user", "content": "Test"}],
        "plan": [{"tool": "task_list", "args": {}}],
        "current_step": 1,
        "status": "executing",
        "budget": {
            "max_steps": 5,
            "steps_used": 2,
            "max_tokens": 5000,
            "tokens_used": 1000,
            "max_wall_time_seconds": 120.0,
            "wall_time_used": 30.0,
        },
        "flags": {
            "dry_run": True,
            "enable_reflection": False,
            "enable_verification": True,
            "require_confirmation": False,
        },
    }

    state = AgentState.from_dict(data)

    assert state.trace_id == "test-456"
    assert state.user == "bob"
    assert len(state.messages) == 1
    assert len(state.plan) == 1
    assert state.current_step == 1
    assert state.status == "executing"
    assert state.budget.steps_used == 2
    assert state.flags.dry_run is True


def test_agent_state_round_trip():
    """Test agent state serialization round trip."""
    original = AgentState(
        trace_id="test-789",
        user="charlie",
        messages=[{"role": "user", "content": "Do something"}],
        plan=[{"tool": "task_create", "args": {"title": "Task 1"}}],
        current_step=0,
    )
    original.budget.steps_used = 3
    original.flags.dry_run = True

    data = original.to_dict()
    restored = AgentState.from_dict(data)

    assert restored.trace_id == original.trace_id
    assert restored.user == original.user
    assert len(restored.messages) == len(original.messages)
    assert len(restored.plan) == len(original.plan)
    assert restored.current_step == original.current_step
    assert restored.budget.steps_used == original.budget.steps_used
    assert restored.flags.dry_run == original.flags.dry_run


def test_agent_state_error_tracking():
    """Test agent state error tracking."""
    state = AgentState(trace_id="test-error")
    assert state.error is None
    assert state.retry_count == 0

    state.error = "Something went wrong"
    state.retry_count = 1

    assert state.error == "Something went wrong"
    assert state.retry_count == 1


def test_agent_state_tool_results():
    """Test agent state tool results tracking."""
    state = AgentState(trace_id="test-results")
    assert state.tool_results == []

    state.tool_results.append(
        {
            "status": "ok",
            "data": {"id": "task-1"},
            "tool": "task_create",
            "step": 0,
        }
    )

    assert len(state.tool_results) == 1
    assert state.tool_results[0]["status"] == "ok"

