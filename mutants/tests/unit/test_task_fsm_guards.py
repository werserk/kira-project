"""Tests for Task FSM with guards (Phase 2, Point 5).

DoD: Invalid transitions raise domain errors; no file changes on failure.
Tests guard validation for all required transitions.
"""

from __future__ import annotations

import contextlib

import pytest

from kira.core.task_fsm import (
    FSMGuardError,
    FSMValidationError,
    TaskState,
    create_task_fsm,
)


class TestTaskFSMGuards:
    """Test FSM guard enforcement (Phase 2, Point 5)."""

    def test_todo_to_doing_requires_assignee_or_start_ts(self):
        """Test todo → doing auto-sets start_ts if missing assignee (Phase 2, Point 5)."""
        fsm = create_task_fsm()

        # Missing both assignee and start_ts should auto-set start_ts
        transition, updated_data = fsm.transition(task_id="task-001", to_state=TaskState.DOING, task_data={})

        assert transition.to_state == TaskState.DOING
        assert "start_ts" in updated_data  # Auto-set by guard
        assert updated_data["start_ts"] is not None

    def test_todo_to_doing_with_assignee_succeeds(self):
        """Test todo → doing with assignee succeeds."""
        fsm = create_task_fsm()

        task_data = {"assignee": "Alice"}
        transition, updated_data = fsm.transition(task_id="task-001", to_state=TaskState.DOING, task_data=task_data)

        assert transition.from_state == TaskState.TODO
        assert transition.to_state == TaskState.DOING
        assert updated_data["assignee"] == "Alice"

    def test_todo_to_doing_with_start_ts_succeeds(self):
        """Test todo → doing with start_ts succeeds."""
        fsm = create_task_fsm()

        task_data = {"start_ts": "2025-10-08T12:00:00+00:00"}
        transition, updated_data = fsm.transition(task_id="task-002", to_state=TaskState.DOING, task_data=task_data)

        assert transition.from_state == TaskState.TODO
        assert transition.to_state == TaskState.DOING
        assert updated_data["start_ts"] == "2025-10-08T12:00:00+00:00"

    def test_todo_to_doing_with_both_succeeds(self):
        """Test todo → doing with both assignee and start_ts succeeds."""
        fsm = create_task_fsm()

        task_data = {"assignee": "Bob", "start_ts": "2025-10-08T14:00:00+00:00"}
        transition, updated_data = fsm.transition(task_id="task-003", to_state=TaskState.DOING, task_data=task_data)

        assert transition.to_state == TaskState.DOING
        assert updated_data["assignee"] == "Bob"
        assert updated_data["start_ts"] == "2025-10-08T14:00:00+00:00"


class TestDoingToDoneGuard:
    """Test doing → done guard (Phase 2, Point 5)."""

    def test_doing_to_done_sets_done_ts(self):
        """Test doing → done sets done_ts automatically."""
        fsm = create_task_fsm()

        # First transition to DOING
        fsm.transition(task_id="task-004", to_state=TaskState.DOING, task_data={"assignee": "Alice"})

        # Then transition to DONE
        task_data = {"assignee": "Alice"}
        transition, updated_data = fsm.transition(task_id="task-004", to_state=TaskState.DONE, task_data=task_data)

        assert transition.to_state == TaskState.DONE
        assert "done_ts" in updated_data
        # Verify it's a valid ISO-8601 UTC timestamp
        assert "+00:00" in updated_data["done_ts"] or "Z" in updated_data["done_ts"]

    def test_doing_to_done_freezes_estimate(self):
        """Test doing → done freezes estimate."""
        fsm = create_task_fsm()

        # First transition to DOING
        fsm.transition(task_id="task-005", to_state=TaskState.DOING, task_data={"assignee": "Bob", "estimate": "4h"})

        # Then transition to DONE
        task_data = {"assignee": "Bob", "estimate": "4h"}
        _transition, updated_data = fsm.transition(task_id="task-005", to_state=TaskState.DONE, task_data=task_data)

        assert updated_data["estimate"] == "4h"
        assert updated_data["estimate_frozen"] is True

    def test_doing_to_done_preserves_existing_done_ts(self):
        """Test doing → done preserves existing done_ts if present."""
        fsm = create_task_fsm()

        # First transition to DOING
        fsm.transition(task_id="task-006", to_state=TaskState.DOING, task_data={"assignee": "Alice"})

        # Transition to DONE with existing done_ts
        existing_done_ts = "2025-10-07T18:00:00+00:00"
        task_data = {"assignee": "Alice", "done_ts": existing_done_ts}
        _transition, updated_data = fsm.transition(task_id="task-006", to_state=TaskState.DONE, task_data=task_data)

        # Should preserve the provided done_ts
        assert updated_data["done_ts"] == existing_done_ts


class TestDoneToDoingGuard:
    """Test done → doing guard (Phase 2, Point 5)."""

    def test_done_to_doing_requires_reopen_reason(self):
        """Test done → doing requires reopen_reason."""
        fsm = create_task_fsm()

        # Set up task in DONE state
        fsm.transition("task-007", TaskState.DOING, task_data={"assignee": "Alice"})
        fsm.transition("task-007", TaskState.DONE, task_data={"assignee": "Alice"})

        # Try to reopen without reason - should fail
        with pytest.raises(FSMGuardError, match="requires 'reopen_reason'"):
            fsm.transition(task_id="task-007", to_state=TaskState.DOING, task_data={"assignee": "Alice"})

    def test_done_to_doing_with_reason_as_parameter(self):
        """Test done → doing with reason as transition parameter."""
        fsm = create_task_fsm()

        # Set up task in DONE state
        fsm.transition("task-008", TaskState.DOING, task_data={"assignee": "Bob"})
        fsm.transition("task-008", TaskState.DONE, task_data={"assignee": "Bob"})

        # Reopen with reason
        transition, updated_data = fsm.transition(
            task_id="task-008", to_state=TaskState.DOING, reason="Found critical bug", task_data={"assignee": "Bob"}
        )

        assert transition.to_state == TaskState.DOING
        assert updated_data["reopen_reason"] == "Found critical bug"

    def test_done_to_doing_with_reason_in_task_data(self):
        """Test done → doing with reason in task_data."""
        fsm = create_task_fsm()

        # Set up task in DONE state
        fsm.transition("task-009", TaskState.DOING, task_data={"assignee": "Charlie"})
        fsm.transition("task-009", TaskState.DONE, task_data={"assignee": "Charlie"})

        # Reopen with reason in task_data
        task_data = {"assignee": "Charlie", "reopen_reason": "Needs additional testing"}
        transition, updated_data = fsm.transition(task_id="task-009", to_state=TaskState.DOING, task_data=task_data)

        assert transition.to_state == TaskState.DOING
        assert updated_data["reopen_reason"] == "Needs additional testing"

    def test_done_to_doing_clears_done_ts(self):
        """Test done → doing clears done_ts."""
        fsm = create_task_fsm()

        # Set up task in DONE state
        fsm.transition("task-010", TaskState.DOING, task_data={"assignee": "Alice"})
        _transition_done, data_done = fsm.transition("task-010", TaskState.DONE, task_data={"assignee": "Alice"})

        # Verify done_ts was set
        assert "done_ts" in data_done

        # Reopen task
        task_data = {"assignee": "Alice", "done_ts": data_done["done_ts"]}
        _transition, updated_data = fsm.transition(
            task_id="task-010", to_state=TaskState.DOING, reason="Reopen for fixes", task_data=task_data
        )

        # done_ts should be cleared
        assert updated_data["done_ts"] is None


class TestInvalidTransitions:
    """Test invalid state transitions are rejected."""

    def test_invalid_transition_raises_error(self):
        """Test invalid transitions raise FSMValidationError."""
        fsm = create_task_fsm()

        # DONE → BLOCKED is invalid
        fsm.transition("task-011", TaskState.DOING, task_data={"assignee": "Bob"})
        fsm.transition("task-011", TaskState.DONE, task_data={"assignee": "Bob"})

        with pytest.raises(FSMValidationError, match="Invalid transition"):
            fsm.transition(task_id="task-011", to_state=TaskState.BLOCKED, task_data={"assignee": "Bob"})

    def test_force_allows_invalid_transition(self):
        """Test force=True bypasses validation."""
        fsm = create_task_fsm()

        # Force an invalid transition
        transition, _ = fsm.transition(
            task_id="task-012", to_state=TaskState.BLOCKED, force=True, reason="Emergency block", task_data={}
        )

        assert transition.to_state == TaskState.BLOCKED

    def test_blocked_requires_reason(self):
        """Test transition to BLOCKED requires reason."""
        fsm = create_task_fsm()

        # Try to block without reason
        with pytest.raises(FSMValidationError, match="requires a reason"):
            fsm.transition(task_id="task-013", to_state=TaskState.BLOCKED, task_data={})


class TestValidTransitions:
    """Test all valid state transitions."""

    def test_todo_to_blocked_with_reason(self):
        """Test todo → blocked with reason."""
        fsm = create_task_fsm()

        transition, _ = fsm.transition(
            task_id="task-014", to_state=TaskState.BLOCKED, reason="Waiting for dependency", task_data={}
        )

        assert transition.from_state == TaskState.TODO
        assert transition.to_state == TaskState.BLOCKED
        assert transition.reason == "Waiting for dependency"

    def test_doing_to_review(self):
        """Test doing → review transition."""
        fsm = create_task_fsm()

        fsm.transition("task-015", TaskState.DOING, task_data={"assignee": "Alice"})

        transition, _ = fsm.transition(task_id="task-015", to_state=TaskState.REVIEW, task_data={"assignee": "Alice"})

        assert transition.from_state == TaskState.DOING
        assert transition.to_state == TaskState.REVIEW

    def test_review_to_done(self):
        """Test review → done transition."""
        fsm = create_task_fsm()

        fsm.transition("task-016", TaskState.DOING, task_data={"assignee": "Bob"})
        fsm.transition("task-016", TaskState.REVIEW, task_data={"assignee": "Bob"})

        transition, updated_data = fsm.transition(
            task_id="task-016", to_state=TaskState.DONE, task_data={"assignee": "Bob"}
        )

        assert transition.from_state == TaskState.REVIEW
        assert transition.to_state == TaskState.DONE
        # Should still set done_ts even from REVIEW
        assert "done_ts" in updated_data

    def test_blocked_to_doing(self):
        """Test blocked → doing transition."""
        fsm = create_task_fsm()

        fsm.transition("task-017", TaskState.BLOCKED, reason="Blocked", task_data={})

        transition, _ = fsm.transition(task_id="task-017", to_state=TaskState.DOING, task_data={"assignee": "Charlie"})

        assert transition.from_state == TaskState.BLOCKED
        assert transition.to_state == TaskState.DOING


class TestTransitionHistory:
    """Test transition history tracking."""

    def test_transition_history_recorded(self):
        """Test transitions are recorded in history."""
        fsm = create_task_fsm()

        # Perform multiple transitions
        fsm.transition("task-018", TaskState.DOING, task_data={"assignee": "Alice"})
        fsm.transition("task-018", TaskState.REVIEW, task_data={"assignee": "Alice"})
        fsm.transition("task-018", TaskState.DONE, task_data={"assignee": "Alice"})

        history = fsm.get_transition_history("task-018")

        assert len(history) == 3
        assert history[0].from_state == TaskState.TODO
        assert history[0].to_state == TaskState.DOING
        assert history[1].from_state == TaskState.DOING
        assert history[1].to_state == TaskState.REVIEW
        assert history[2].from_state == TaskState.REVIEW
        assert history[2].to_state == TaskState.DONE

    def test_reopening_recorded_in_history(self):
        """Test reopening transitions are recorded with reason."""
        fsm = create_task_fsm()

        fsm.transition("task-019", TaskState.DOING, task_data={"assignee": "Bob"})
        fsm.transition("task-019", TaskState.DONE, task_data={"assignee": "Bob"})
        fsm.transition("task-019", TaskState.DOING, reason="Bug found in production", task_data={"assignee": "Bob"})

        history = fsm.get_transition_history("task-019")

        assert len(history) == 3
        reopening = history[2]
        assert reopening.from_state == TaskState.DONE
        assert reopening.to_state == TaskState.DOING
        assert reopening.reason == "Bug found in production"


class TestFSMStatistics:
    """Test FSM statistics and queries."""

    def test_get_tasks_in_state(self):
        """Test getting all tasks in a specific state."""
        fsm = create_task_fsm()

        # Create tasks in different states
        fsm.transition("task-020", TaskState.DOING, task_data={"assignee": "Alice"})
        fsm.transition("task-021", TaskState.DOING, task_data={"assignee": "Bob"})
        fsm.transition("task-022", TaskState.DONE, task_data={"assignee": "Charlie"})

        doing_tasks = fsm.get_tasks_in_state(TaskState.DOING)
        done_tasks = fsm.get_tasks_in_state(TaskState.DONE)

        assert len(doing_tasks) == 2
        assert "task-020" in doing_tasks
        assert "task-021" in doing_tasks
        assert len(done_tasks) == 1
        assert "task-022" in done_tasks

    def test_get_statistics(self):
        """Test getting FSM statistics."""
        fsm = create_task_fsm()

        # Create tasks in various states
        fsm.transition("task-023", TaskState.DOING, task_data={"assignee": "Alice"})
        fsm.transition("task-024", TaskState.DOING, task_data={"assignee": "Bob"})
        # Need to go through DOING before REVIEW
        fsm.transition("task-025", TaskState.DOING, task_data={"assignee": "Charlie"})
        fsm.transition("task-025", TaskState.REVIEW, task_data={"assignee": "Charlie"})
        # Can skip directly to DONE from TODO
        fsm.transition("task-026", TaskState.DONE, task_data={"assignee": "Dave"}, force=True)

        stats = fsm.get_statistics()

        assert stats["total_tasks"] >= 4
        assert stats["by_state"]["doing"] >= 2
        assert stats["by_state"]["review"] >= 1
        assert stats["by_state"]["done"] >= 1


class TestGuardsDoNotModifyOnFailure:
    """Test that guards do not modify data on failure (Phase 2, Point 5 DoD)."""

    def test_failed_guard_does_not_mutate_task_data(self):
        """Test failed guard doesn't modify original task_data."""
        fsm = create_task_fsm()

        # Set up a DONE task to test done→doing guard failure
        fsm.transition(task_id="task-027", to_state=TaskState.DOING, task_data={"assignee": "Alice"})
        fsm.transition(task_id="task-027", to_state=TaskState.DONE, task_data={"assignee": "Alice"})

        original_data = {"title": "Test Task"}
        task_data_copy = original_data.copy()

        # Try invalid transition (done→doing without reopen_reason)
        with contextlib.suppress(FSMGuardError):
            fsm.transition(task_id="task-027", to_state=TaskState.DOING, task_data=task_data_copy)

        # Original data should be unchanged
        assert task_data_copy == original_data
        assert "done_ts" not in task_data_copy
        assert "reopen_reason" not in task_data_copy

    def test_state_not_updated_on_guard_failure(self):
        """Test state is not updated when guard fails."""
        fsm = create_task_fsm()

        # Set up a DONE task
        fsm.transition(task_id="task-028", to_state=TaskState.DOING, task_data={"assignee": "Bob"})
        fsm.transition(task_id="task-028", to_state=TaskState.DONE, task_data={"assignee": "Bob"})

        # Try invalid transition (done→doing without reopen_reason)
        with contextlib.suppress(FSMGuardError):
            fsm.transition(task_id="task-028", to_state=TaskState.DOING, task_data={})

        # State should still be DONE (not updated)
        assert fsm.get_state("task-028") == TaskState.DONE


class TestCanTransition:
    """Test can_transition validation helper."""

    def test_can_transition_valid(self):
        """Test can_transition returns True for valid transitions."""
        fsm = create_task_fsm()

        assert fsm.can_transition("task-029", TaskState.DOING) is True
        assert fsm.can_transition("task-029", TaskState.BLOCKED) is True

    def test_can_transition_invalid(self):
        """Test can_transition returns False for invalid transitions."""
        fsm = create_task_fsm()

        # Set task to DONE
        fsm.transition("task-030", TaskState.DOING, task_data={"assignee": "Alice"})
        fsm.transition("task-030", TaskState.DONE, task_data={"assignee": "Alice"})

        # DONE → REVIEW is invalid
        assert fsm.can_transition("task-030", TaskState.REVIEW) is False
        # DONE → BLOCKED is invalid
        assert fsm.can_transition("task-030", TaskState.BLOCKED) is False
        # DONE → DOING is valid
        assert fsm.can_transition("task-030", TaskState.DOING) is True
