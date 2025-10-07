"""Task Finite State Machine (ADR-014).

Implements task state management with explicit transitions and hooks
for timeboxing, review, and completion workflows.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .events import EventBus

__all__ = [
    "TaskState",
    "TaskTransition",
    "TaskFSM",
    "FSMValidationError",
    "create_task_fsm",
]


class TaskState(str, Enum):
    """Task states in the FSM."""

    TODO = "todo"
    DOING = "doing"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"


@dataclass
class TaskTransition:
    """Record of a task state transition."""

    from_state: TaskState
    to_state: TaskState
    timestamp: datetime
    reason: str | None = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)


class FSMValidationError(Exception):
    """Raised when FSM validation fails."""

    pass


class TaskFSM:
    """Task Finite State Machine (ADR-014).

    Manages task state transitions with validation, event emission,
    and hook execution for automated workflows.

    States: todo → doing → review → done | blocked

    Hooks:
    - enter_doing: Create timebox in calendar
    - enter_review: Draft review email
    - enter_done: Update rollup, close timebox
    - enter_blocked: Notify, set blocked_reason

    Example:
        >>> fsm = TaskFSM(event_bus=event_bus)
        >>> fsm.transition(task_id="task-123", to_state=TaskState.DOING)
        >>> # Emits: task.enter_doing event
        >>> # Hook: Creates timebox in calendar
    """

    # Valid transitions mapping
    VALID_TRANSITIONS: dict[TaskState, list[TaskState]] = {
        TaskState.TODO: [TaskState.DOING, TaskState.BLOCKED, TaskState.DONE],
        TaskState.DOING: [TaskState.REVIEW, TaskState.BLOCKED, TaskState.DONE],
        TaskState.REVIEW: [TaskState.DONE, TaskState.DOING, TaskState.BLOCKED],
        TaskState.DONE: [TaskState.DOING],  # Can reopen
        TaskState.BLOCKED: [TaskState.TODO, TaskState.DOING],
    }

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize Task FSM.

        Parameters
        ----------
        event_bus
            Event bus for emitting transition events
        logger
            Optional logger for structured logging
        """
        self.event_bus = event_bus
        self.logger = logger
        self._task_states: dict[str, TaskState] = {}
        self._transition_history: dict[str, list[TaskTransition]] = {}
        self._hooks: dict[TaskState, list[Callable]] = {
            TaskState.DOING: [],
            TaskState.REVIEW: [],
            TaskState.DONE: [],
            TaskState.BLOCKED: [],
        }

    def register_hook(self, state: TaskState, hook: Callable[[dict[str, Any]], None]) -> None:
        """Register a hook to execute on entering a state.

        Parameters
        ----------
        state
            State to hook into
        hook
            Function to call with transition context
        """
        if state in self._hooks:
            self._hooks[state].append(hook)
            if self.logger:
                self.logger.debug(f"Registered hook for state: {state.value}")

    def get_state(self, task_id: str) -> TaskState:
        """Get current state of a task.

        Parameters
        ----------
        task_id
            Task identifier

        Returns
        -------
        TaskState
            Current state (defaults to TODO)
        """
        return self._task_states.get(task_id, TaskState.TODO)

    def can_transition(self, task_id: str, to_state: TaskState) -> bool:
        """Check if transition is valid.

        Parameters
        ----------
        task_id
            Task identifier
        to_state
            Target state

        Returns
        -------
        bool
            True if transition is valid
        """
        current_state = self.get_state(task_id)
        return to_state in self.VALID_TRANSITIONS.get(current_state, [])

    def transition(
        self,
        task_id: str,
        to_state: TaskState,
        *,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        force: bool = False,
    ) -> TaskTransition:
        """Transition task to new state.

        Parameters
        ----------
        task_id
            Task identifier
        to_state
            Target state
        reason
            Optional reason for transition (required for BLOCKED)
        metadata
            Additional metadata for transition
        force
            Force transition even if invalid (use with caution)

        Returns
        -------
        TaskTransition
            Transition record

        Raises
        ------
        FSMValidationError
            If transition is invalid and not forced
        """
        current_state = self.get_state(task_id)

        # Validate transition
        if not force and not self.can_transition(task_id, to_state):
            raise FSMValidationError(
                f"Invalid transition: {current_state.value} → {to_state.value} "
                f"for task {task_id}"
            )

        # Validate blocked state requires reason
        if to_state == TaskState.BLOCKED and not reason:
            raise FSMValidationError(
                f"Transition to BLOCKED requires a reason for task {task_id}"
            )

        # Create transition record
        transition = TaskTransition(
            from_state=current_state,
            to_state=to_state,
            timestamp=datetime.now(timezone.utc),
            reason=reason,
            metadata=metadata or {},
        )

        # Update state
        self._task_states[task_id] = to_state

        # Record transition
        if task_id not in self._transition_history:
            self._transition_history[task_id] = []
        self._transition_history[task_id].append(transition)

        # Log transition
        if self.logger:
            self.logger.info(
                f"Task transition: {task_id} {current_state.value} → {to_state.value}",
                extra={
                    "task_id": task_id,
                    "from_state": current_state.value,
                    "to_state": to_state.value,
                    "trace_id": transition.trace_id,
                    "reason": reason,
                },
            )

        # Emit event
        self._emit_transition_event(task_id, transition)

        # Execute hooks
        self._execute_hooks(task_id, to_state, transition)

        return transition

    def _emit_transition_event(self, task_id: str, transition: TaskTransition) -> None:
        """Emit event for state transition.

        Parameters
        ----------
        task_id
            Task identifier
        transition
            Transition record
        """
        if not self.event_bus:
            return

        # Emit specific transition event
        event_name = f"task.enter_{transition.to_state.value}"

        payload = {
            "task_id": task_id,
            "entity_id": task_id,  # Alias for compatibility
            "from_state": transition.from_state.value,
            "to_state": transition.to_state.value,
            "timestamp": transition.timestamp.isoformat(),
            "reason": transition.reason,
            "trace_id": transition.trace_id,
            **transition.metadata,
        }

        self.event_bus.publish(event_name, payload, correlation_id=transition.trace_id)

        if self.logger:
            self.logger.debug(
                f"Emitted event: {event_name}",
                extra={
                    "event": event_name,
                    "task_id": task_id,
                    "trace_id": transition.trace_id,
                },
            )

    def _execute_hooks(
        self,
        task_id: str,
        state: TaskState,
        transition: TaskTransition,
    ) -> None:
        """Execute registered hooks for state entry.

        Parameters
        ----------
        task_id
            Task identifier
        state
            State being entered
        transition
            Transition record
        """
        hooks = self._hooks.get(state, [])

        if not hooks:
            return

        context = {
            "task_id": task_id,
            "from_state": transition.from_state.value,
            "to_state": transition.to_state.value,
            "timestamp": transition.timestamp.isoformat(),
            "reason": transition.reason,
            "trace_id": transition.trace_id,
            **transition.metadata,
        }

        for hook in hooks:
            try:
                hook(context)

                if self.logger:
                    self.logger.debug(
                        f"Executed hook for {state.value}",
                        extra={
                            "task_id": task_id,
                            "state": state.value,
                            "hook": hook.__name__,
                        },
                    )

            except Exception as exc:
                if self.logger:
                    self.logger.error(
                        f"Hook execution failed: {exc}",
                        extra={
                            "task_id": task_id,
                            "state": state.value,
                            "hook": hook.__name__,
                            "error": str(exc),
                        },
                    )

    def get_transition_history(self, task_id: str) -> list[TaskTransition]:
        """Get transition history for a task.

        Parameters
        ----------
        task_id
            Task identifier

        Returns
        -------
        list[TaskTransition]
            List of transitions in chronological order
        """
        return self._transition_history.get(task_id, [])

    def get_tasks_in_state(self, state: TaskState) -> list[str]:
        """Get all tasks in a given state.

        Parameters
        ----------
        state
            State to filter by

        Returns
        -------
        list[str]
            List of task IDs
        """
        return [
            task_id
            for task_id, task_state in self._task_states.items()
            if task_state == state
        ]

    def get_statistics(self) -> dict[str, Any]:
        """Get FSM statistics.

        Returns
        -------
        dict
            Statistics by state
        """
        stats = {
            "by_state": {},
            "total_tasks": len(self._task_states),
            "total_transitions": sum(len(h) for h in self._transition_history.values()),
        }

        for state in TaskState:
            tasks_in_state = self.get_tasks_in_state(state)
            stats["by_state"][state.value] = len(tasks_in_state)

        return stats


def create_task_fsm(
    *,
    event_bus: EventBus | None = None,
    logger: Any = None,
) -> TaskFSM:
    """Factory function to create Task FSM.

    Parameters
    ----------
    event_bus
        Event bus for event emission
    logger
        Optional logger

    Returns
    -------
    TaskFSM
        Configured FSM instance

    Example:
        >>> fsm = create_task_fsm(event_bus=event_bus)
        >>> fsm.transition("task-123", TaskState.DOING)
    """
    return TaskFSM(event_bus=event_bus, logger=logger)

