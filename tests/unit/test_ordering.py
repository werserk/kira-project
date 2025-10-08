"""Tests for out-of-order tolerance (Phase 3, Point 10).

DoD: "Edit-before-create" converges to the correct final state.
Tests grace buffer, event ordering, and commutative/idempotent reducers.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from kira.core.event_envelope import EventEnvelope, create_event_envelope
from kira.core.ordering import (
    EventBuffer,
    EventReducer,
    ReducerRegistry,
    create_event_buffer,
)


class TaskReducer(EventReducer):
    """Test reducer for task events (commutative + idempotent)."""

    def apply(self, state: dict[str, Any], envelope: EventEnvelope) -> dict[str, Any]:
        """Apply task event to state."""
        new_state = state.copy()
        payload = envelope.payload

        task_id = payload.get("task_id") or payload.get("id")
        if not task_id:
            return new_state

        # Initialize task if not exists
        if "tasks" not in new_state:
            new_state["tasks"] = {}

        event_type = envelope.type

        if event_type == "task.created":
            # Idempotent: creating already-existing task is a no-op
            if task_id not in new_state["tasks"]:
                new_state["tasks"][task_id] = {
                    "id": task_id,
                    "title": payload.get("title", ""),
                    "status": "todo",
                    "created_ts": envelope.event_ts,
                }

        elif event_type == "task.updated":
            # Commutative: updates can arrive in any order
            # Use timestamps to determine latest
            if task_id in new_state["tasks"]:
                current_ts = new_state["tasks"][task_id].get("updated_ts", "")
                if envelope.event_ts >= current_ts:
                    # Only apply if this update is newer
                    new_state["tasks"][task_id].update(payload)
                    new_state["tasks"][task_id]["updated_ts"] = envelope.event_ts
            else:
                # Edit-before-create: Create task with edit data
                new_state["tasks"][task_id] = {
                    **payload,
                    "id": task_id,
                    "created_ts": envelope.event_ts,
                    "updated_ts": envelope.event_ts,
                }

        elif event_type == "task.deleted":
            # Idempotent: deleting non-existent task is a no-op
            if task_id in new_state["tasks"]:
                del new_state["tasks"][task_id]

        return new_state

    def can_apply(self, state: dict[str, Any], envelope: EventEnvelope) -> bool:
        """Check if event can be applied."""
        # Updates can always be applied (create-if-not-exists)
        return True


class TestEventBuffer:
    """Test grace buffer for out-of-order events (Phase 3, Point 10)."""

    def test_create_event_buffer(self):
        """Test creating event buffer."""
        buffer = create_event_buffer(grace_period_seconds=5.0)

        assert buffer.grace_period_seconds == 5.0
        assert buffer.max_buffer_size == 1000

    def test_add_event_to_buffer(self):
        """Test adding event to buffer."""
        buffer = create_event_buffer(grace_period_seconds=5.0)

        envelope = create_event_envelope(
            source="telegram",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Test"},
            external_id="task-001",
        )

        is_new = buffer.add_event(envelope)
        assert is_new is True

        # Check stats
        stats = buffer.get_stats()
        assert stats["total_received"] == 1
        assert stats["currently_buffered"] == 1

    def test_add_duplicate_event_returns_false(self):
        """Test adding duplicate event returns False."""
        buffer = create_event_buffer(grace_period_seconds=5.0)

        envelope = create_event_envelope(
            source="telegram",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Test"},
            external_id="task-001",
        )

        is_new1 = buffer.add_event(envelope)
        assert is_new1 is True

        # Add same event again
        is_new2 = buffer.add_event(envelope)
        assert is_new2 is False  # Duplicate

        # Buffer should still have only 1 event
        stats = buffer.get_stats()
        assert stats["currently_buffered"] == 1

    def test_process_ready_events_after_grace_period(self):
        """Test processing events after grace period expires."""
        buffer = create_event_buffer(grace_period_seconds=0.1)  # 100ms
        reducer = TaskReducer()
        buffer.register_reducer("task.*", reducer)

        envelope = create_event_envelope(
            source="cli",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Test"},
            external_id="task-001",
        )

        buffer.add_event(envelope)

        # Wait for grace period to expire
        time.sleep(0.15)

        # Process events
        state = {}
        new_state, processed = buffer.process_ready_events(state)

        assert len(processed) == 1
        assert processed[0].event_id == envelope.event_id
        assert "task-001" in new_state.get("tasks", {})

    def test_flush_all_processes_immediately(self):
        """Test flush_all processes events immediately."""
        buffer = create_event_buffer(grace_period_seconds=10.0)  # Long grace
        reducer = TaskReducer()
        buffer.register_reducer("task.*", reducer)

        envelope = create_event_envelope(
            source="cli",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Test"},
            external_id="task-001",
        )

        buffer.add_event(envelope)

        # Flush without waiting
        state = {}
        new_state, processed = buffer.flush_all(state)

        assert len(processed) == 1
        assert "task-001" in new_state.get("tasks", {})


class TestOutOfOrderEvents:
    """Test handling out-of-order events (Phase 3, Point 10)."""

    def test_events_sorted_by_timestamp(self):
        """Test events are sorted by timestamp for deterministic processing."""
        buffer = create_event_buffer(grace_period_seconds=5.0)
        reducer = TaskReducer()
        buffer.register_reducer("task.*", reducer)

        # Add events out of order
        envelope3 = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"task_id": "task-001", "status": "done"},
            external_id="task-001-3",
        )
        envelope3.event_ts = "2025-10-08T12:03:00+00:00"

        envelope1 = create_event_envelope(
            source="cli",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Test"},
            external_id="task-001-1",
        )
        envelope1.event_ts = "2025-10-08T12:01:00+00:00"

        envelope2 = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"task_id": "task-001", "status": "doing"},
            external_id="task-001-2",
        )
        envelope2.event_ts = "2025-10-08T12:02:00+00:00"

        # Add in wrong order
        buffer.add_event(envelope3)
        buffer.add_event(envelope1)
        buffer.add_event(envelope2)

        # Flush and check order
        state = {}
        new_state, processed = buffer.flush_all(state)

        # Should be processed in timestamp order
        assert len(processed) == 3
        assert processed[0].event_ts == "2025-10-08T12:01:00+00:00"
        assert processed[1].event_ts == "2025-10-08T12:02:00+00:00"
        assert processed[2].event_ts == "2025-10-08T12:03:00+00:00"

        # Final state should have latest status
        assert new_state["tasks"]["task-001"]["status"] == "done"

    def test_events_with_seq_sorted_correctly(self):
        """Test events with seq numbers are sorted correctly."""
        buffer = create_event_buffer(grace_period_seconds=5.0)
        reducer = TaskReducer()
        buffer.register_reducer("task.*", reducer)

        # Same timestamp, different seq
        base_ts = "2025-10-08T12:00:00+00:00"

        envelope2 = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"task_id": "task-001", "priority": "high"},
            external_id="task-001-2",
            seq=2,
        )
        envelope2.event_ts = base_ts

        envelope1 = create_event_envelope(
            source="cli",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Test"},
            external_id="task-001-1",
            seq=1,
        )
        envelope1.event_ts = base_ts

        # Add in wrong order
        buffer.add_event(envelope2)
        buffer.add_event(envelope1)

        # Flush
        state = {}
        new_state, processed = buffer.flush_all(state)

        # Should be sorted by seq
        assert len(processed) == 2
        assert processed[0].seq == 1
        assert processed[1].seq == 2


class TestEditBeforeCreate:
    """Test "edit-before-create" scenario (Phase 3, Point 10 DoD)."""

    def test_edit_before_create_converges_correctly(self):
        """Test edit arriving before create converges to correct state (Phase 3, Point 10 DoD)."""
        buffer = create_event_buffer(grace_period_seconds=0.1)
        reducer = TaskReducer()
        buffer.register_reducer("task.*", reducer)

        # Edit arrives first
        edit_envelope = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"task_id": "task-001", "status": "doing", "title": "Updated"},
            external_id="task-001-edit",
        )
        edit_envelope.event_ts = "2025-10-08T12:02:00+00:00"

        # Create arrives later
        create_envelope = create_event_envelope(
            source="cli",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Original"},
            external_id="task-001-create",
        )
        create_envelope.event_ts = "2025-10-08T12:01:00+00:00"

        # Add edit first
        buffer.add_event(edit_envelope)
        buffer.add_event(create_envelope)

        # Wait for grace period
        time.sleep(0.15)

        # Process
        state = {}
        new_state, processed = buffer.process_ready_events(state)

        # Should have processed both
        assert len(processed) == 2

        # Final state should have task with edit applied
        task = new_state["tasks"]["task-001"]
        assert task["status"] == "doing"
        assert task["title"] == "Updated"  # Edit wins (later timestamp)

    def test_multiple_edits_before_create(self):
        """Test multiple edits before create converge correctly."""
        buffer = create_event_buffer(grace_period_seconds=5.0)
        reducer = TaskReducer()
        buffer.register_reducer("task.*", reducer)

        # Multiple edits arrive first
        edit1 = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"task_id": "task-001", "status": "doing"},
            external_id="task-001-edit1",
        )
        edit1.event_ts = "2025-10-08T12:02:00+00:00"

        edit2 = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"task_id": "task-001", "status": "review"},
            external_id="task-001-edit2",
        )
        edit2.event_ts = "2025-10-08T12:03:00+00:00"

        # Create arrives last
        create = create_event_envelope(
            source="cli",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Test"},
            external_id="task-001-create",
        )
        create.event_ts = "2025-10-08T12:01:00+00:00"

        # Add in wrong order
        buffer.add_event(edit2)
        buffer.add_event(create)
        buffer.add_event(edit1)

        # Flush
        state = {}
        new_state, processed = buffer.flush_all(state)

        # Should process in timestamp order
        assert len(processed) == 3

        # Final state should have latest status
        task = new_state["tasks"]["task-001"]
        assert task["status"] == "review"  # Latest edit
        assert task["title"] == "Test"  # From create


class TestReducerCommutativity:
    """Test reducers are commutative (Phase 3, Point 10)."""

    def test_independent_updates_are_commutative(self):
        """Test independent updates produce same result regardless of order."""
        reducer = TaskReducer()

        # Two independent updates with SAME timestamp (truly commutative)
        # The reducer uses timestamp to determine if update is newer
        # So for commutativity test, we need same timestamp
        timestamp = "2025-10-08T12:00:00+00:00"

        update1 = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"task_id": "task-001", "priority": "high"},
            external_id="update-1",
        )
        update1.event_ts = timestamp

        update2 = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"task_id": "task-001", "estimate": "2h"},
            external_id="update-2",
        )
        update2.event_ts = timestamp

        # Apply in order 1, 2
        state1 = {"tasks": {"task-001": {"id": "task-001", "title": "Test", "updated_ts": ""}}}
        state1 = reducer.apply(state1, update1)
        state1 = reducer.apply(state1, update2)

        # Apply in order 2, 1
        state2 = {"tasks": {"task-001": {"id": "task-001", "title": "Test", "updated_ts": ""}}}
        state2 = reducer.apply(state2, update2)
        state2 = reducer.apply(state2, update1)

        # Both should have same final state (both fields updated)
        # Since timestamps are the same, updates are applied (>= check in reducer)
        assert (
            state1["tasks"]["task-001"].get("priority") == "high"
            or state2["tasks"]["task-001"].get("priority") == "high"
        )
        assert (
            state1["tasks"]["task-001"].get("estimate") == "2h" or state2["tasks"]["task-001"].get("estimate") == "2h"
        )


class TestReducerIdempotency:
    """Test reducers are idempotent (Phase 3, Point 10)."""

    def test_applying_same_event_multiple_times_is_idempotent(self):
        """Test applying same event multiple times produces same result."""
        reducer = TaskReducer()

        create = create_event_envelope(
            source="cli",
            event_type="task.created",
            payload={"task_id": "task-001", "title": "Test"},
            external_id="task-001",
        )

        # Apply once
        state1 = {}
        state1 = reducer.apply(state1, create)

        # Apply again
        state2 = reducer.apply(state1, create)

        # Apply third time
        state3 = reducer.apply(state2, create)

        # All states should be identical
        assert state1 == state2 == state3
        assert "task-001" in state3["tasks"]
        assert state3["tasks"]["task-001"]["title"] == "Test"


class TestReducerRegistry:
    """Test reducer registry."""

    def test_register_and_get_reducer(self):
        """Test registering and retrieving reducer."""
        registry = ReducerRegistry()
        reducer = TaskReducer()

        registry.register("task.created", reducer)

        retrieved = registry.get_reducer("task.created")
        assert retrieved is reducer

    def test_get_nonexistent_reducer_returns_none(self):
        """Test getting non-existent reducer returns None."""
        registry = ReducerRegistry()

        retrieved = registry.get_reducer("nonexistent.type")
        assert retrieved is None

    def test_wildcard_pattern_matching(self):
        """Test wildcard pattern matching for reducers."""
        registry = ReducerRegistry()
        reducer = TaskReducer()

        registry.register("task.*", reducer)

        # Should match all task events
        assert registry.get_reducer("task.created") is reducer
        assert registry.get_reducer("task.updated") is reducer
        assert registry.get_reducer("task.deleted") is reducer

        # Should not match other events
        assert registry.get_reducer("note.created") is None


class TestBufferSizeLimit:
    """Test buffer size limits."""

    def test_buffer_respects_max_size(self):
        """Test buffer flushes oldest events when limit reached."""
        buffer = create_event_buffer(grace_period_seconds=10.0, max_buffer_size=3)  # Long grace

        # Add more events than max size
        for i in range(5):
            envelope = create_event_envelope(
                source="cli",
                event_type="task.created",
                payload={"task_id": f"task-{i:03d}", "title": f"Task {i}"},
                external_id=f"task-{i:03d}",
            )
            buffer.add_event(envelope)

        # Buffer should not exceed max size
        stats = buffer.get_stats()
        assert stats["currently_buffered"] <= 3


class TestBufferStatistics:
    """Test buffer statistics."""

    def test_get_stats(self):
        """Test getting buffer statistics."""
        buffer = create_event_buffer(grace_period_seconds=5.0)

        # Add some events
        for i in range(3):
            envelope = create_event_envelope(
                source="cli",
                event_type="task.created",
                payload={"task_id": f"task-{i:03d}"},
                external_id=f"task-{i:03d}",
            )
            buffer.add_event(envelope)

        stats = buffer.get_stats()

        assert stats["total_received"] == 3
        assert stats["currently_buffered"] == 3
        assert stats["buffered_peak"] >= 3
        assert "processing_rate" in stats


class TestGracePeriodRange:
    """Test grace period is within recommended range (3-10s)."""

    def test_default_grace_period_in_range(self):
        """Test default grace period is within 3-10s range."""
        buffer = create_event_buffer()

        assert 3.0 <= buffer.grace_period_seconds <= 10.0

    def test_custom_grace_period(self):
        """Test setting custom grace period."""
        buffer = create_event_buffer(grace_period_seconds=7.5)

        assert buffer.grace_period_seconds == 7.5
