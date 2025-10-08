"""Tests for Task FSM guards (Phase 1, Point 4)."""

import pytest

from kira.core.task_fsm import FSMGuardError, FSMValidationError, TaskFSM, TaskState


def test_guard_todo_to_doing_requires_assignee():
    """Test todo → doing requires assignee OR start_ts."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # Should fail: no assignee and no start_ts
    task_data = {"title": "Test Task"}
    
    with pytest.raises(FSMGuardError, match="requires either 'assignee' or 'start_ts'"):
        fsm.transition(task_id, TaskState.DOING, task_data=task_data)


def test_guard_todo_to_doing_with_assignee():
    """Test todo → doing succeeds with assignee."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    task_data = {"title": "Test Task", "assignee": "alice@example.com"}
    
    transition, updated_data = fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    
    assert transition.to_state == TaskState.DOING
    assert updated_data["assignee"] == "alice@example.com"


def test_guard_todo_to_doing_with_start_ts():
    """Test todo → doing succeeds with start_ts."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    task_data = {"title": "Test Task", "start_ts": "2025-10-08T12:00:00+00:00"}
    
    transition, updated_data = fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    
    assert transition.to_state == TaskState.DOING
    assert updated_data["start_ts"] == "2025-10-08T12:00:00+00:00"


def test_guard_todo_to_doing_with_both():
    """Test todo → doing succeeds with both assignee and start_ts."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    task_data = {
        "title": "Test Task",
        "assignee": "alice@example.com",
        "start_ts": "2025-10-08T12:00:00+00:00",
    }
    
    transition, updated_data = fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    
    assert transition.to_state == TaskState.DOING


def test_guard_doing_to_done_sets_done_ts():
    """Test doing → done sets done_ts automatically."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # First transition to DOING
    task_data = {"title": "Test Task", "assignee": "alice@example.com"}
    fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    
    # Transition to DONE
    transition, updated_data = fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    
    assert transition.to_state == TaskState.DONE
    assert "done_ts" in updated_data
    assert updated_data["done_ts"] is not None
    # Should be ISO-8601 UTC format
    assert "+00:00" in updated_data["done_ts"]


def test_guard_doing_to_done_preserves_existing_done_ts():
    """Test doing → done preserves existing done_ts if already set."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # First transition to DOING
    task_data = {"title": "Test Task", "assignee": "alice@example.com"}
    fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    
    # Transition to DONE with existing done_ts
    task_data["done_ts"] = "2025-10-08T10:00:00+00:00"
    transition, updated_data = fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    
    # Should preserve the provided done_ts
    assert updated_data["done_ts"] == "2025-10-08T10:00:00+00:00"


def test_guard_doing_to_done_freezes_estimate():
    """Test doing → done freezes estimate."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # First transition to DOING
    task_data = {"title": "Test Task", "assignee": "alice@example.com", "estimate": "2h"}
    fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    
    # Transition to DONE
    transition, updated_data = fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    
    assert updated_data["estimate"] == "2h"
    assert updated_data["estimate_frozen"] is True


def test_guard_doing_to_done_without_estimate():
    """Test doing → done works even without estimate."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # First transition to DOING
    task_data = {"title": "Test Task", "assignee": "alice@example.com"}
    fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    
    # Transition to DONE without estimate
    transition, updated_data = fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    
    assert transition.to_state == TaskState.DONE
    assert "estimate_frozen" not in updated_data  # No estimate to freeze


def test_guard_done_to_doing_requires_reopen_reason():
    """Test done → doing requires reopen_reason."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # Get to DONE state
    task_data = {"title": "Test Task", "assignee": "alice@example.com"}
    fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    
    # Try to reopen without reason
    with pytest.raises(FSMGuardError, match="requires 'reopen_reason'"):
        fsm.transition(task_id, TaskState.DOING, task_data=task_data)


def test_guard_done_to_doing_with_reopen_reason():
    """Test done → doing succeeds with reopen_reason."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # Get to DONE state
    task_data = {"title": "Test Task", "assignee": "alice@example.com"}
    fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    _, task_data_after_done = fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    
    # done_ts should be set
    assert "done_ts" in task_data_after_done
    
    # Reopen with reason
    transition, updated_data = fsm.transition(
        task_id,
        TaskState.DOING,
        reason="Found critical bug",
        task_data=task_data_after_done,
    )
    
    assert transition.to_state == TaskState.DOING
    assert updated_data["reopen_reason"] == "Found critical bug"
    # done_ts should be cleared on reopen
    assert updated_data["done_ts"] is None


def test_guard_done_to_doing_with_reopen_reason_in_task_data():
    """Test done → doing accepts reopen_reason from task_data."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # Get to DONE state
    task_data = {"title": "Test Task", "assignee": "alice@example.com"}
    fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    
    # Reopen with reason in task_data
    task_data["reopen_reason"] = "Needs more testing"
    transition, updated_data = fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    
    assert transition.to_state == TaskState.DOING
    assert updated_data["reopen_reason"] == "Needs more testing"


def test_guards_do_not_apply_with_force():
    """Test guards can be bypassed with force=True."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # Force todo → doing without assignee or start_ts
    task_data = {"title": "Test Task"}
    
    transition, updated_data = fsm.transition(
        task_id, TaskState.DOING, task_data=task_data, force=True
    )
    
    # Should succeed despite guard
    assert transition.to_state == TaskState.DOING


def test_invalid_transition_raises_fsm_validation_error():
    """Test invalid state transitions raise FSMValidationError."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # Invalid transition: TODO → REVIEW (not allowed)
    task_data = {"title": "Test Task"}
    
    with pytest.raises(FSMValidationError, match="Invalid transition"):
        fsm.transition(task_id, TaskState.REVIEW, task_data=task_data)


def test_guard_errors_do_not_modify_state():
    """Test that guard errors do NOT modify task state."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # Try invalid transition
    task_data = {"title": "Test Task"}
    
    try:
        fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    except FSMGuardError:
        pass
    
    # State should still be TODO
    assert fsm.get_state(task_id) == TaskState.TODO


def test_full_task_lifecycle_with_guards():
    """Test complete task lifecycle with all guards."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    # Start with TODO (implicit)
    assert fsm.get_state(task_id) == TaskState.TODO
    
    # TODO → DOING (with assignee)
    task_data = {
        "title": "Test Task",
        "assignee": "alice@example.com",
        "estimate": "4h",
    }
    _, task_data = fsm.transition(task_id, TaskState.DOING, task_data=task_data)
    assert fsm.get_state(task_id) == TaskState.DOING
    
    # DOING → DONE (sets done_ts, freezes estimate)
    _, task_data = fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    assert fsm.get_state(task_id) == TaskState.DONE
    assert "done_ts" in task_data
    assert task_data["estimate_frozen"] is True
    
    # DONE → DOING (requires reopen_reason)
    _, task_data = fsm.transition(
        task_id,
        TaskState.DOING,
        reason="Found regression",
        task_data=task_data,
    )
    assert fsm.get_state(task_id) == TaskState.DOING
    assert task_data["reopen_reason"] == "Found regression"
    assert task_data["done_ts"] is None
    
    # DOING → DONE again
    _, task_data = fsm.transition(task_id, TaskState.DONE, task_data=task_data)
    assert fsm.get_state(task_id) == TaskState.DONE
    assert "done_ts" in task_data


def test_blocked_state_requires_reason():
    """Test BLOCKED state always requires reason (existing behavior)."""
    fsm = TaskFSM()
    task_id = "task-123"
    
    task_data = {"title": "Test Task"}
    
    # Should fail without reason
    with pytest.raises(FSMValidationError, match="BLOCKED requires a reason"):
        fsm.transition(task_id, TaskState.BLOCKED, task_data=task_data)
    
    # Should succeed with reason
    transition, _ = fsm.transition(
        task_id,
        TaskState.BLOCKED,
        reason="Waiting for API access",
        task_data=task_data,
    )
    assert transition.to_state == TaskState.BLOCKED
    assert transition.reason == "Waiting for API access"

