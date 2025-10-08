"""Tests for ordering tolerance and event sequencing (Phase 2, Point 10)."""

import time

import pytest

from kira.core.event_envelope import EventEnvelope, create_event_envelope
from kira.core.ordering import (
    BufferedEvent,
    EventBuffer,
    EventReducer,
    ReducerRegistry,
    create_event_buffer,
)


# Test reducers

class TaskReducer(EventReducer):
    """Test reducer for task events."""
    
    def apply(self, state: dict, envelope: EventEnvelope) -> dict:
        """Apply task event to state."""
        new_state = state.copy()
        task_id = envelope.payload.get("task_id")
        
        if envelope.type == "task.created":
            if "tasks" not in new_state:
                new_state["tasks"] = {}
            new_state["tasks"][task_id] = {
                "id": task_id,
                "title": envelope.payload.get("title", ""),
                "status": "todo",
                "created_ts": envelope.event_ts,
            }
        elif envelope.type == "task.updated":
            if "tasks" in new_state and task_id in new_state["tasks"]:
                new_state["tasks"][task_id].update(envelope.payload)
                new_state["tasks"][task_id]["updated_ts"] = envelope.event_ts
        elif envelope.type == "task.completed":
            if "tasks" in new_state and task_id in new_state["tasks"]:
                new_state["tasks"][task_id]["status"] = "done"
                new_state["tasks"][task_id]["completed_ts"] = envelope.event_ts
        
        return new_state
    
    def can_apply(self, state: dict, envelope: EventEnvelope) -> bool:
        """Check if event can be applied."""
        task_id = envelope.payload.get("task_id")
        
        # Create can always apply
        if envelope.type == "task.created":
            return True
        
        # Update/complete requires task to exist
        if envelope.type in ["task.updated", "task.completed"]:
            return (
                "tasks" in state
                and task_id in state["tasks"]
            )
        
        return True


def test_buffered_event_age():
    """Test BufferedEvent age calculation."""
    envelope = create_event_envelope(
        source="test",
        event_type="test.event",
        payload={},
    )
    
    buffered = BufferedEvent(envelope=envelope, received_at=time.time())
    
    # Age should be near zero
    assert buffered.age_seconds < 0.1
    
    # Wait a bit
    time.sleep(0.1)
    
    # Age should have increased
    assert buffered.age_seconds >= 0.1


def test_reducer_registry():
    """Test reducer registry."""
    registry = ReducerRegistry()
    reducer = TaskReducer()
    
    registry.register("task.*", reducer)
    
    # Exact match should not find it
    assert registry.get_reducer("task.*") == reducer
    
    # Wildcard match should find it
    assert registry.get_reducer("task.created") == reducer
    assert registry.get_reducer("task.updated") == reducer


def test_event_buffer_initialization():
    """Test event buffer initialization."""
    buffer = EventBuffer(grace_period_seconds=3.0, max_buffer_size=500)
    
    assert buffer.grace_period_seconds == 3.0
    assert buffer.max_buffer_size == 500


def test_event_buffer_add_event():
    """Test adding event to buffer."""
    buffer = create_event_buffer()
    
    envelope = create_event_envelope(
        source="test",
        event_type="test.event",
        payload={"entity_id": "123"},
    )
    
    # First add should return True (new event)
    assert buffer.add_event(envelope) is True
    
    # Second add should return False (duplicate)
    assert buffer.add_event(envelope) is False


def test_event_buffer_register_reducer():
    """Test registering reducer with buffer."""
    buffer = create_event_buffer()
    reducer = TaskReducer()
    
    buffer.register_reducer("task.*", reducer)
    
    # Should be able to process task events
    assert buffer._reducers.get_reducer("task.created") == reducer


def test_event_buffer_process_after_grace_period():
    """Test processing events after grace period expires."""
    buffer = create_event_buffer(grace_period_seconds=0.1)  # 100ms grace
    reducer = TaskReducer()
    buffer.register_reducer("task.*", reducer)
    
    # Add event
    envelope = create_event_envelope(
        source="test",
        event_type="task.created",
        payload={"task_id": "task-1", "title": "Test"},
    )
    buffer.add_event(envelope)
    
    # Immediately process - should not process yet (grace period not expired)
    state = {}
    state, processed = buffer.process_ready_events(state)
    assert len(processed) == 0
    
    # Wait for grace period
    time.sleep(0.15)
    
    # Now should process
    state, processed = buffer.process_ready_events(state)
    assert len(processed) == 1
    assert "tasks" in state
    assert "task-1" in state["tasks"]


def test_event_buffer_flush_all():
    """Test flushing all buffered events."""
    buffer = create_event_buffer()
    reducer = TaskReducer()
    buffer.register_reducer("task.*", reducer)
    
    # Add multiple events
    for i in range(3):
        envelope = create_event_envelope(
            source="test",
            event_type="task.created",
            payload={"task_id": f"task-{i}", "title": f"Task {i}"},
            seq=i,
        )
        buffer.add_event(envelope)
    
    # Flush all
    state = {}
    state, processed = buffer.flush_all(state)
    
    assert len(processed) == 3
    assert len(state.get("tasks", {})) == 3


def test_event_buffer_idempotency():
    """Test buffer prevents duplicate processing."""
    buffer = create_event_buffer(grace_period_seconds=0.0)  # Process immediately
    reducer = TaskReducer()
    buffer.register_reducer("task.*", reducer)
    
    envelope = create_event_envelope(
        source="test",
        event_type="task.created",
        payload={"task_id": "task-1", "title": "Test"},
    )
    
    # Add twice
    buffer.add_event(envelope)
    buffer.add_event(envelope)
    
    # Flush
    state = {}
    state, processed = buffer.flush_all(state)
    
    # Should only process once (idempotent)
    assert len(processed) == 1


def test_event_buffer_sorts_by_timestamp():
    """Test buffer sorts events by timestamp."""
    buffer = create_event_buffer(grace_period_seconds=0.0)
    reducer = TaskReducer()
    buffer.register_reducer("task.*", reducer)
    
    # Add events in reverse chronological order
    for i in range(3):
        envelope = EventEnvelope(
            event_id=f"event-{i}",
            event_ts=f"2025-10-08T12:00:0{3-i}+00:00",  # Reverse order
            source="test",
            type="task.created",
            payload={"task_id": f"task-{i}", "title": f"Task {i}"},
            seq=3 - i,  # Reverse sequence
        )
        buffer.add_event(envelope)
    
    # Flush
    state = {}
    state, processed = buffer.flush_all(state)
    
    # Should be processed in chronological order (sorted by timestamp)
    assert processed[0].event_id == "event-2"  # earliest timestamp
    assert processed[1].event_id == "event-1"
    assert processed[2].event_id == "event-0"  # latest timestamp


def test_event_buffer_handles_edit_before_create():
    """Test handling 'edit before create' scenario."""
    buffer = create_event_buffer(grace_period_seconds=0.1)
    reducer = TaskReducer()
    buffer.register_reducer("task.*", reducer)
    
    # Add update before create (out of order)
    update_envelope = EventEnvelope(
        event_id="update-1",
        event_ts="2025-10-08T12:00:02+00:00",
        source="test",
        type="task.updated",
        payload={"task_id": "task-1", "title": "Updated Title"},
        seq=2,
    )
    buffer.add_event(update_envelope)
    
    # Add create event
    create_envelope = EventEnvelope(
        event_id="create-1",
        event_ts="2025-10-08T12:00:01+00:00",
        source="test",
        type="task.created",
        payload={"task_id": "task-1", "title": "Original Title"},
        seq=1,
    )
    buffer.add_event(create_envelope)
    
    # Wait for grace period
    time.sleep(0.15)
    
    # Process - should handle in correct order
    state = {}
    state, processed = buffer.process_ready_events(state)
    
    # Should process create first, then update
    assert len(processed) == 2
    assert processed[0].type == "task.created"
    assert processed[1].type == "task.updated"
    
    # Final state should have updated title
    assert state["tasks"]["task-1"]["title"] == "Updated Title"


def test_event_buffer_deterministic_replays():
    """Test deterministic replay of events."""
    # Scenario 1: Events in order
    buffer1 = create_event_buffer(grace_period_seconds=0.0)
    reducer1 = TaskReducer()
    buffer1.register_reducer("task.*", reducer1)
    
    events = [
        EventEnvelope(
            event_id="1",
            event_ts="2025-10-08T12:00:01+00:00",
            source="test",
            type="task.created",
            payload={"task_id": "task-1", "title": "Test"},
            seq=1,
        ),
        EventEnvelope(
            event_id="2",
            event_ts="2025-10-08T12:00:02+00:00",
            source="test",
            type="task.updated",
            payload={"task_id": "task-1", "title": "Updated"},
            seq=2,
        ),
        EventEnvelope(
            event_id="3",
            event_ts="2025-10-08T12:00:03+00:00",
            source="test",
            type="task.completed",
            payload={"task_id": "task-1"},
            seq=3,
        ),
    ]
    
    for event in events:
        buffer1.add_event(event)
    
    state1 = {}
    state1, _ = buffer1.flush_all(state1)
    
    # Scenario 2: Same events in different order
    buffer2 = create_event_buffer(grace_period_seconds=0.0)
    reducer2 = TaskReducer()
    buffer2.register_reducer("task.*", reducer2)
    
    # Add in reverse order
    for event in reversed(events):
        buffer2.add_event(event)
    
    state2 = {}
    state2, _ = buffer2.flush_all(state2)
    
    # Final states should be identical (deterministic)
    assert state1 == state2


def test_event_buffer_get_stats():
    """Test getting buffer statistics."""
    buffer = create_event_buffer()
    
    # Add some events
    for i in range(5):
        envelope = create_event_envelope(
            source="test",
            event_type="test.event",
            payload={"id": f"event-{i}"},
        )
        buffer.add_event(envelope)
    
    stats = buffer.get_stats()
    
    assert stats["total_received"] == 5
    assert stats["currently_buffered"] == 5
    assert stats["unique_entities"] > 0


def test_event_buffer_max_size_limit():
    """Test buffer respects max size limit."""
    buffer = create_event_buffer(max_buffer_size=10)
    
    # Add more events than limit
    for i in range(20):
        envelope = create_event_envelope(
            source="test",
            event_type="test.event",
            payload={"id": f"event-{i}"},
        )
        buffer.add_event(envelope)
    
    stats = buffer.get_stats()
    
    # Should not exceed limit
    assert stats["currently_buffered"] <= 10


def test_dod_out_of_order_sequences_converge():
    """Test DoD: Out-of-order sequences converge to same final state."""
    # Create three different orderings of the same events
    events = [
        EventEnvelope(
            event_id="create",
            event_ts="2025-10-08T12:00:01+00:00",
            source="test",
            type="task.created",
            payload={"task_id": "task-1", "title": "Original"},
            seq=1,
        ),
        EventEnvelope(
            event_id="update1",
            event_ts="2025-10-08T12:00:02+00:00",
            source="test",
            type="task.updated",
            payload={"task_id": "task-1", "title": "First Update"},
            seq=2,
        ),
        EventEnvelope(
            event_id="update2",
            event_ts="2025-10-08T12:00:03+00:00",
            source="test",
            type="task.updated",
            payload={"task_id": "task-1", "title": "Second Update"},
            seq=3,
        ),
        EventEnvelope(
            event_id="complete",
            event_ts="2025-10-08T12:00:04+00:00",
            source="test",
            type="task.completed",
            payload={"task_id": "task-1"},
            seq=4,
        ),
    ]
    
    # Test different orderings
    orderings = [
        events,  # In order
        list(reversed(events)),  # Reverse order
        [events[2], events[0], events[3], events[1]],  # Random order 1
        [events[3], events[1], events[0], events[2]],  # Random order 2
    ]
    
    final_states = []
    
    for ordering in orderings:
        buffer = create_event_buffer(grace_period_seconds=0.0)
        reducer = TaskReducer()
        buffer.register_reducer("task.*", reducer)
        
        for event in ordering:
            buffer.add_event(event)
        
        state = {}
        state, _ = buffer.flush_all(state)
        final_states.append(state)
    
    # All final states should be identical
    first_state = final_states[0]
    for state in final_states[1:]:
        assert state == first_state, "Out-of-order sequences did not converge to same state"
    
    # Verify final state is correct
    assert first_state["tasks"]["task-1"]["title"] == "Second Update"
    assert first_state["tasks"]["task-1"]["status"] == "done"


def test_create_event_buffer_factory():
    """Test factory function for creating buffer."""
    buffer = create_event_buffer(grace_period_seconds=7.5, max_buffer_size=2000)
    
    assert buffer.grace_period_seconds == 7.5
    assert buffer.max_buffer_size == 2000

