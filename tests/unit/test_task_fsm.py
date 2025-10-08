"""Tests for Task FSM (ADR-014)."""

from datetime import UTC, datetime
from typing import Never
from unittest.mock import MagicMock, Mock

import pytest

from kira.core.task_fsm import (
    FSMValidationError,
    TaskFSM,
    TaskState,
    TaskTransition,
    create_task_fsm,
)


class TestTaskState:
    """Test TaskState enum."""

    def test_all_states_defined(self):
        """Test all required states are defined."""
        assert TaskState.TODO == "todo"
        assert TaskState.DOING == "doing"
        assert TaskState.REVIEW == "review"
        assert TaskState.DONE == "done"
        assert TaskState.BLOCKED == "blocked"


class TestTaskTransition:
    """Test TaskTransition dataclass."""

    def test_create_transition(self):
        """Test creating transition record."""
        transition = TaskTransition(
            from_state=TaskState.TODO,
            to_state=TaskState.DOING,
            timestamp=datetime.now(UTC),
            reason="Starting work",
        )

        assert transition.from_state == TaskState.TODO
        assert transition.to_state == TaskState.DOING
        assert transition.reason == "Starting work"
        assert transition.trace_id is not None

    def test_transition_with_metadata(self):
        """Test transition with metadata."""
        metadata = {"user_id": "user-123", "time_hint": 60}

        transition = TaskTransition(
            from_state=TaskState.DOING,
            to_state=TaskState.DONE,
            timestamp=datetime.now(UTC),
            metadata=metadata,
        )

        assert transition.metadata == metadata
        assert transition.metadata["user_id"] == "user-123"


class TestTaskFSM:
    """Test TaskFSM class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.event_bus = MagicMock()
        self.logger = MagicMock()
        self.fsm = TaskFSM(event_bus=self.event_bus, logger=self.logger)

    def test_initialization(self):
        """Test FSM initialization."""
        assert self.fsm.event_bus is self.event_bus
        assert self.fsm.logger is self.logger
        assert len(self.fsm._task_states) == 0
        assert len(self.fsm._transition_history) == 0

    def test_default_state_is_todo(self):
        """Test default state is TODO."""
        state = self.fsm.get_state("task-123")
        assert state == TaskState.TODO

    def test_valid_transitions_defined(self):
        """Test all valid transitions are defined."""
        assert TaskState.DOING in TaskFSM.VALID_TRANSITIONS[TaskState.TODO]
        assert TaskState.REVIEW in TaskFSM.VALID_TRANSITIONS[TaskState.DOING]
        assert TaskState.DONE in TaskFSM.VALID_TRANSITIONS[TaskState.REVIEW]
        assert TaskState.TODO in TaskFSM.VALID_TRANSITIONS[TaskState.BLOCKED]

    def test_can_transition_valid(self):
        """Test checking valid transitions."""
        # TODO -> DOING is valid
        assert self.fsm.can_transition("task-123", TaskState.DOING)

        # TODO -> REVIEW is invalid
        assert not self.fsm.can_transition("task-123", TaskState.REVIEW)

    def test_transition_todo_to_doing(self):
        """Test transitioning from TODO to DOING."""
        transition, _ = self.fsm.transition("task-123", TaskState.DOING)

        assert transition.from_state == TaskState.TODO
        assert transition.to_state == TaskState.DOING
        assert self.fsm.get_state("task-123") == TaskState.DOING

    def test_transition_invalid_raises_error(self):
        """Test invalid transition raises error."""
        with pytest.raises(FSMValidationError):
            self.fsm.transition("task-123", TaskState.REVIEW)

    def test_transition_with_force_allows_invalid(self):
        """Test force flag allows invalid transitions."""
        # TODO -> REVIEW is invalid, but force=True allows it
        transition, _ = self.fsm.transition("task-123", TaskState.REVIEW, force=True)

        assert transition.from_state == TaskState.TODO
        assert transition.to_state == TaskState.REVIEW
        assert self.fsm.get_state("task-123") == TaskState.REVIEW

    def test_transition_to_blocked_requires_reason(self):
        """Test transitioning to BLOCKED requires reason."""
        with pytest.raises(FSMValidationError, match="requires a reason"):
            self.fsm.transition("task-123", TaskState.BLOCKED)

    def test_transition_to_blocked_with_reason(self):
        """Test transitioning to BLOCKED with reason."""
        transition, _ = self.fsm.transition("task-123", TaskState.BLOCKED, reason="Waiting for API access")

        assert transition.to_state == TaskState.BLOCKED
        assert transition.reason == "Waiting for API access"

    def test_transition_emits_event(self):
        """Test transition emits correct event."""
        self.fsm.transition("task-123", TaskState.DOING)

        # Check event was published
        self.event_bus.publish.assert_called_once()

        call_args = self.event_bus.publish.call_args
        assert call_args[0][0] == "task.enter_doing"
        assert call_args[0][1]["task_id"] == "task-123"
        assert call_args[0][1]["to_state"] == "doing"

    def test_transition_logs_event(self):
        """Test transition logs to logger."""
        self.fsm.transition("task-123", TaskState.DOING)

        # Check logger was called
        self.logger.info.assert_called()

        call_args = self.logger.info.call_args
        assert "task-123" in call_args[0][0]
        assert "todo → doing" in call_args[0][0]

    def test_transition_history_recorded(self):
        """Test transition history is recorded."""
        self.fsm.transition("task-123", TaskState.DOING)
        self.fsm.transition("task-123", TaskState.REVIEW)
        self.fsm.transition("task-123", TaskState.DONE)

        history = self.fsm.get_transition_history("task-123")

        assert len(history) == 3
        assert history[0].to_state == TaskState.DOING
        assert history[1].to_state == TaskState.REVIEW
        assert history[2].to_state == TaskState.DONE

    def test_transition_with_metadata(self):
        """Test transition with metadata."""
        metadata = {"user_id": "user-123", "time_hint": 60}

        transition, _ = self.fsm.transition("task-123", TaskState.DOING, metadata=metadata)

        assert transition.metadata == metadata

        # Check metadata in event payload
        call_args = self.event_bus.publish.call_args
        assert call_args[0][1]["user_id"] == "user-123"
        assert call_args[0][1]["time_hint"] == 60

    def test_get_tasks_in_state(self):
        """Test getting tasks in a specific state."""
        self.fsm.transition("task-1", TaskState.DOING)
        self.fsm.transition("task-2", TaskState.DOING)
        self.fsm.transition("task-3", TaskState.DOING)
        self.fsm.transition("task-3", TaskState.REVIEW)

        doing_tasks = self.fsm.get_tasks_in_state(TaskState.DOING)
        review_tasks = self.fsm.get_tasks_in_state(TaskState.REVIEW)

        assert len(doing_tasks) == 2
        assert "task-1" in doing_tasks
        assert "task-2" in doing_tasks

        assert len(review_tasks) == 1
        assert "task-3" in review_tasks

    def test_get_statistics(self):
        """Test getting FSM statistics."""
        self.fsm.transition("task-1", TaskState.DOING)
        self.fsm.transition("task-2", TaskState.DOING)
        self.fsm.transition("task-3", TaskState.DOING)
        self.fsm.transition("task-3", TaskState.REVIEW)
        self.fsm.transition("task-1", TaskState.DONE)

        stats = self.fsm.get_statistics()

        assert stats["total_tasks"] == 3
        assert stats["total_transitions"] == 5  # task-1: TODO→DOING→DONE, task-2: TODO→DOING, task-3: TODO→DOING→REVIEW
        assert stats["by_state"]["doing"] == 1
        assert stats["by_state"]["review"] == 1
        assert stats["by_state"]["done"] == 1

    def test_full_workflow_todo_to_done(self):
        """Test full workflow: TODO -> DOING -> REVIEW -> DONE."""
        task_id = "task-full-workflow"

        # Start in TODO (implicit)
        assert self.fsm.get_state(task_id) == TaskState.TODO

        # TODO -> DOING
        self.fsm.transition(task_id, TaskState.DOING)
        assert self.fsm.get_state(task_id) == TaskState.DOING

        # DOING -> REVIEW
        self.fsm.transition(task_id, TaskState.REVIEW)
        assert self.fsm.get_state(task_id) == TaskState.REVIEW

        # REVIEW -> DONE
        self.fsm.transition(task_id, TaskState.DONE)
        assert self.fsm.get_state(task_id) == TaskState.DONE

        # Check history
        history = self.fsm.get_transition_history(task_id)
        assert len(history) == 3


class TestTaskFSMHooks:
    """Test TaskFSM hook system."""

    def setup_method(self):
        """Setup test fixtures."""
        self.event_bus = MagicMock()
        self.logger = MagicMock()
        self.fsm = TaskFSM(event_bus=self.event_bus, logger=self.logger)

    def test_register_hook(self):
        """Test registering a hook."""
        hook_fn = Mock()

        self.fsm.register_hook(TaskState.DOING, hook_fn)

        assert hook_fn in self.fsm._hooks[TaskState.DOING]

    def test_hook_executes_on_transition(self):
        """Test hook executes on state entry."""
        hook_fn = Mock()

        self.fsm.register_hook(TaskState.DOING, hook_fn)
        self.fsm.transition("task-123", TaskState.DOING)

        # Check hook was called
        hook_fn.assert_called_once()

        # Check hook received context
        context = hook_fn.call_args[0][0]
        assert context["task_id"] == "task-123"
        assert context["to_state"] == "doing"

    def test_multiple_hooks_execute(self):
        """Test multiple hooks execute in order."""
        hook1 = Mock()
        hook2 = Mock()

        self.fsm.register_hook(TaskState.DOING, hook1)
        self.fsm.register_hook(TaskState.DOING, hook2)

        self.fsm.transition("task-123", TaskState.DOING)

        hook1.assert_called_once()
        hook2.assert_called_once()

    def test_hook_failure_logged(self):
        """Test hook failure is logged but doesn't fail transition."""

        def failing_hook(context) -> Never:
            raise ValueError("Hook failed!")

        self.fsm.register_hook(TaskState.DOING, failing_hook)

        # Transition should succeed despite hook failure
        transition, _ = self.fsm.transition("task-123", TaskState.DOING)

        assert transition.to_state == TaskState.DOING
        assert self.fsm.get_state("task-123") == TaskState.DOING

        # Check error was logged
        self.logger.error.assert_called()

    def test_hook_receives_metadata(self):
        """Test hook receives metadata from transition."""
        hook_fn = Mock()
        metadata = {"time_hint": 120, "priority": "high"}

        self.fsm.register_hook(TaskState.DOING, hook_fn)
        self.fsm.transition("task-123", TaskState.DOING, metadata=metadata)

        context = hook_fn.call_args[0][0]
        assert context["time_hint"] == 120
        assert context["priority"] == "high"

    def test_timeboxing_hook_integration(self):
        """Test timeboxing hook is called on enter_doing."""
        timebox_created = []

        def create_timebox_hook(context) -> None:
            """Mock timeboxing hook."""
            timebox_created.append(
                {
                    "task_id": context["task_id"],
                    "time_hint": context.get("time_hint", 60),
                }
            )

        self.fsm.register_hook(TaskState.DOING, create_timebox_hook)
        self.fsm.transition("task-123", TaskState.DOING, metadata={"time_hint": 90})

        assert len(timebox_created) == 1
        assert timebox_created[0]["task_id"] == "task-123"
        assert timebox_created[0]["time_hint"] == 90


class TestTaskFSMEventPayloads:
    """Test event payloads emitted by FSM."""

    def setup_method(self):
        """Setup test fixtures."""
        self.event_bus = MagicMock()
        self.fsm = TaskFSM(event_bus=self.event_bus)

    def test_event_payload_structure(self):
        """Test event payload has correct structure."""
        self.fsm.transition("task-123", TaskState.DOING)

        call_args = self.event_bus.publish.call_args
        event_name, payload = call_args[0]
        correlation_id = call_args[1]["correlation_id"]

        assert event_name == "task.enter_doing"
        assert payload["task_id"] == "task-123"
        assert payload["entity_id"] == "task-123"  # Alias
        assert payload["from_state"] == "todo"
        assert payload["to_state"] == "doing"
        assert "timestamp" in payload
        assert "trace_id" in payload
        assert correlation_id == payload["trace_id"]

    def test_event_includes_reason(self):
        """Test event includes reason when provided."""
        self.fsm.transition("task-123", TaskState.BLOCKED, reason="API down")

        call_args = self.event_bus.publish.call_args
        payload = call_args[0][1]

        assert payload["reason"] == "API down"

    def test_different_events_for_different_states(self):
        """Test different events are emitted for different states."""
        task_id = "task-456"

        # DOING
        self.fsm.transition(task_id, TaskState.DOING)
        assert self.event_bus.publish.call_args[0][0] == "task.enter_doing"

        # REVIEW
        self.fsm.transition(task_id, TaskState.REVIEW)
        assert self.event_bus.publish.call_args[0][0] == "task.enter_review"

        # DONE
        self.fsm.transition(task_id, TaskState.DONE)
        assert self.event_bus.publish.call_args[0][0] == "task.enter_done"


class TestTaskFSMWorkflows:
    """Test realistic FSM workflows."""

    def setup_method(self):
        """Setup test fixtures."""
        self.event_bus = MagicMock()
        self.logger = MagicMock()
        self.fsm = TaskFSM(event_bus=self.event_bus, logger=self.logger)

    def test_blocked_workflow(self):
        """Test workflow with blocking."""
        task_id = "task-blocked"

        # Start work
        self.fsm.transition(task_id, TaskState.DOING)

        # Get blocked
        self.fsm.transition(task_id, TaskState.BLOCKED, reason="Waiting for dependency")
        assert self.fsm.get_state(task_id) == TaskState.BLOCKED

        # Unblock and continue
        self.fsm.transition(task_id, TaskState.DOING)
        assert self.fsm.get_state(task_id) == TaskState.DOING

        # Complete
        self.fsm.transition(task_id, TaskState.DONE)

        history = self.fsm.get_transition_history(task_id)
        assert len(history) == 4

    def test_reopen_done_task(self):
        """Test reopening a done task."""
        task_id = "task-reopen"

        # Complete task
        self.fsm.transition(task_id, TaskState.DOING)
        self.fsm.transition(task_id, TaskState.DONE)
        assert self.fsm.get_state(task_id) == TaskState.DONE

        # Reopen with reason
        self.fsm.transition(task_id, TaskState.DOING, reason="Found issue that needs fixing")
        assert self.fsm.get_state(task_id) == TaskState.DOING

    def test_skip_review_workflow(self):
        """Test workflow skipping review."""
        task_id = "task-skip-review"

        # Go directly from DOING to DONE
        self.fsm.transition(task_id, TaskState.DOING)
        self.fsm.transition(task_id, TaskState.DONE)

        assert self.fsm.get_state(task_id) == TaskState.DONE

        history = self.fsm.get_transition_history(task_id)
        assert len(history) == 2
        assert history[1].to_state == TaskState.DONE

    def test_multiple_tasks_concurrent(self):
        """Test multiple tasks with concurrent transitions."""
        self.fsm.transition("task-1", TaskState.DOING)
        self.fsm.transition("task-2", TaskState.DOING)
        self.fsm.transition("task-3", TaskState.DOING)

        self.fsm.transition("task-1", TaskState.DONE)
        self.fsm.transition("task-2", TaskState.REVIEW)

        assert self.fsm.get_state("task-1") == TaskState.DONE
        assert self.fsm.get_state("task-2") == TaskState.REVIEW
        assert self.fsm.get_state("task-3") == TaskState.DOING

        stats = self.fsm.get_statistics()
        assert stats["total_tasks"] == 3
        assert stats["by_state"]["done"] == 1
        assert stats["by_state"]["review"] == 1
        assert stats["by_state"]["doing"] == 1


class TestFactoryFunction:
    """Test create_task_fsm factory function."""

    def test_create_task_fsm(self):
        """Test factory creates FSM instance."""
        event_bus = MagicMock()
        logger = MagicMock()

        fsm = create_task_fsm(event_bus=event_bus, logger=logger)

        assert isinstance(fsm, TaskFSM)
        assert fsm.event_bus is event_bus
        assert fsm.logger is logger

    def test_create_without_dependencies(self):
        """Test factory works without event bus/logger."""
        fsm = create_task_fsm()

        assert isinstance(fsm, TaskFSM)
        assert fsm.event_bus is None
        assert fsm.logger is None


class TestTimeboxingCoverage:
    """Test timeboxing coverage metrics (ADR-014 requirement)."""

    def setup_method(self):
        """Setup test fixtures."""
        self.event_bus = MagicMock()
        self.fsm = TaskFSM(event_bus=self.event_bus)
        self.timeboxed_tasks = set()

        def track_timebox(context) -> None:
            self.timeboxed_tasks.add(context["task_id"])

        self.fsm.register_hook(TaskState.DOING, track_timebox)

    def test_timeboxing_hook_called_for_all_doing_tasks(self):
        """Test timeboxing hook is called for all tasks entering DOING."""
        tasks = [f"task-{i}" for i in range(10)]

        for task_id in tasks:
            self.fsm.transition(task_id, TaskState.DOING)

        assert len(self.timeboxed_tasks) == 10
        assert all(task_id in self.timeboxed_tasks for task_id in tasks)

    def test_calculate_timebox_coverage(self):
        """Test calculating timebox coverage percentage."""
        # Create 10 tasks in DOING state
        for i in range(10):
            self.fsm.transition(f"task-{i}", TaskState.DOING)

        # All should be timeboxed via hook
        doing_tasks = self.fsm.get_tasks_in_state(TaskState.DOING)
        coverage = len(self.timeboxed_tasks) / len(doing_tasks) if doing_tasks else 0

        # Should meet 90% coverage requirement
        assert coverage >= 0.90
