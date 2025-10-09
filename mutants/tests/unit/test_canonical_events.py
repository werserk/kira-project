"""Tests for canonical events module."""

from __future__ import annotations

from kira.core.canonical_events import (
    CANONICAL_EVENTS,
    EventDefinition,
    get_event_definition,
    get_events_by_category,
    is_canonical_event,
)


def test_event_definition_defaults():
    """Test EventDefinition with None values uses defaults."""
    event = EventDefinition(
        name="test.event",
        category="test",
        description="Test event",
        payload_schema=None,
        emitted_by=None,
    )

    assert event.payload_schema == {}
    assert event.emitted_by == []


def test_get_event_definition_exists():
    """Test getting existing event definition."""
    # Use a known canonical event
    event = get_event_definition("task.created")
    assert event is not None
    assert event.name == "task.created"
    assert event.category == "task"


def test_get_event_definition_not_exists():
    """Test getting non-existent event definition."""
    event = get_event_definition("nonexistent.event")
    assert event is None


def test_is_canonical_event_true():
    """Test is_canonical_event with existing event."""
    assert is_canonical_event("task.created") is True
    assert is_canonical_event("task.due_soon") is True


def test_is_canonical_event_false():
    """Test is_canonical_event with non-existent event."""
    assert is_canonical_event("nonexistent.event") is False
    assert is_canonical_event("invalid") is False


def test_get_events_by_category():
    """Test getting events by category."""
    task_events = get_events_by_category("task")
    assert len(task_events) > 0
    assert all(event.category == "task" for event in task_events)

    # Check known task events
    event_names = [event.name for event in task_events]
    assert "task.created" in event_names
    assert "task.due_soon" in event_names


def test_get_events_by_category_empty():
    """Test getting events by non-existent category."""
    events = get_events_by_category("nonexistent_category")
    assert events == []


def test_canonical_events_registry():
    """Test that CANONICAL_EVENTS registry is properly populated."""
    assert len(CANONICAL_EVENTS) > 0

    # Check some expected events exist
    expected_events = [
        "task.created",
        "task.due_soon",
        "entity.created",
        "entity.deleted",
        "message.received",
    ]

    for event_name in expected_events:
        assert event_name in CANONICAL_EVENTS
        event = CANONICAL_EVENTS[event_name]
        assert isinstance(event, EventDefinition)
        assert event.name == event_name

