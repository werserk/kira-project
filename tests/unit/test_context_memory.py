"""Unit tests for context memory."""

from __future__ import annotations

import pytest

from kira.agent.context_memory import ContextMemory, EntityFact, create_context_memory


def test_entity_fact_creation() -> None:
    """Test entity fact creation."""
    fact = EntityFact(
        uid="task-123",
        title="Test Task",
        entity_type="task",
        status="todo",
        tags=["work"],
    )

    assert fact.uid == "task-123"
    assert fact.title == "Test Task"
    assert fact.entity_type == "task"
    assert fact.status == "todo"
    assert fact.tags == ["work"]


def test_entity_fact_to_dict() -> None:
    """Test entity fact serialization."""
    fact = EntityFact(
        uid="task-456",
        title="Another Task",
        entity_type="task",
        status="done",
    )

    data = fact.to_dict()

    assert data["uid"] == "task-456"
    assert data["title"] == "Another Task"
    assert data["type"] == "task"
    assert data["status"] == "done"


def test_entity_fact_from_dict() -> None:
    """Test entity fact deserialization."""
    data = {
        "uid": "task-789",
        "title": "Restored Task",
        "type": "task",
        "status": "doing",
        "tags": ["urgent"],
    }

    fact = EntityFact.from_dict(data)

    assert fact.uid == "task-789"
    assert fact.title == "Restored Task"
    assert fact.entity_type == "task"
    assert fact.status == "doing"
    assert fact.tags == ["urgent"]


def test_context_memory_initialization() -> None:
    """Test context memory initialization."""
    memory = ContextMemory(max_facts=10, max_messages=5)

    assert memory.max_facts == 10
    assert memory.max_messages == 5
    assert memory.sessions == {}


def test_context_memory_add_entity_fact() -> None:
    """Test adding entity fact to memory."""
    memory = ContextMemory()
    fact = EntityFact(uid="task-1", title="Task 1", entity_type="task")

    memory.add_entity_fact("session-1", fact)

    assert memory.has_context("session-1")


def test_context_memory_add_message() -> None:
    """Test adding message to memory."""
    memory = ContextMemory()

    memory.add_message("session-1", "user", "Create a task")
    memory.add_message("session-1", "assistant", "Task created")

    assert memory.has_context("session-1")


def test_context_memory_get_last_entity() -> None:
    """Test getting last referenced entity."""
    memory = ContextMemory()

    fact1 = EntityFact(uid="task-1", title="First", entity_type="task")
    fact2 = EntityFact(uid="task-2", title="Second", entity_type="task")

    memory.add_entity_fact("session-1", fact1)
    memory.add_entity_fact("session-1", fact2)

    last_entity = memory.get_last_entity("session-1")

    assert last_entity is not None
    assert last_entity.uid == "task-2"


def test_context_memory_get_last_entity_by_type() -> None:
    """Test getting last entity filtered by type."""
    memory = ContextMemory()

    task_fact = EntityFact(uid="task-1", title="Task", entity_type="task")
    note_fact = EntityFact(uid="note-1", title="Note", entity_type="note")

    memory.add_entity_fact("session-1", task_fact)
    memory.add_entity_fact("session-1", note_fact)

    last_task = memory.get_last_entity("session-1", entity_type="task")

    assert last_task is not None
    assert last_task.entity_type == "task"
    assert last_task.uid == "task-1"


def test_context_memory_get_entity_by_uid() -> None:
    """Test getting entity by UID."""
    memory = ContextMemory()

    fact = EntityFact(uid="task-123", title="Test", entity_type="task")
    memory.add_entity_fact("session-1", fact)

    retrieved = memory.get_entity_by_uid("session-1", "task-123")

    assert retrieved is not None
    assert retrieved.uid == "task-123"
    assert retrieved.title == "Test"


def test_context_memory_set_get_context() -> None:
    """Test setting and getting context values."""
    memory = ContextMemory()

    memory.set_context("session-1", "last_action", "task_create")
    memory.set_context("session-1", "count", 5)

    assert memory.get_context("session-1", "last_action") == "task_create"
    assert memory.get_context("session-1", "count") == 5
    assert memory.get_context("session-1", "missing", "default") == "default"


def test_context_memory_get_facts_summary() -> None:
    """Test getting facts summary."""
    memory = ContextMemory()

    fact1 = EntityFact(uid="task-1", title="First Task", entity_type="task", status="todo")
    fact2 = EntityFact(uid="task-2", title="Second Task", entity_type="task", status="done")

    memory.add_entity_fact("session-1", fact1)
    memory.add_entity_fact("session-1", fact2)

    summary = memory.get_facts_summary("session-1", limit=2)

    assert "task-1" in summary
    assert "First Task" in summary
    assert "task-2" in summary


def test_context_memory_get_facts_summary_empty() -> None:
    """Test facts summary for empty session."""
    memory = ContextMemory()

    summary = memory.get_facts_summary("session-1")

    assert "No recent entities" in summary


def test_context_memory_to_dict() -> None:
    """Test exporting memory to dict."""
    memory = ContextMemory()

    fact = EntityFact(uid="task-1", title="Task", entity_type="task")
    memory.add_entity_fact("session-1", fact)
    memory.add_message("session-1", "user", "Hello")
    memory.set_context("session-1", "key", "value")

    data = memory.to_dict("session-1")

    assert "facts" in data
    assert "messages" in data
    assert "context" in data
    assert len(data["facts"]) == 1
    assert len(data["messages"]) == 1
    assert data["context"]["key"] == "value"


def test_context_memory_from_dict() -> None:
    """Test importing memory from dict."""
    memory = ContextMemory()

    data = {
        "facts": [
            {
                "uid": "task-1",
                "title": "Test Task",
                "type": "task",
                "status": "todo",
            }
        ],
        "messages": [{"role": "user", "content": "Create task"}],
        "context": {"key": "value"},
    }

    memory.from_dict("session-1", data)

    assert memory.has_context("session-1")
    assert memory.get_entity_by_uid("session-1", "task-1") is not None
    assert memory.get_context("session-1", "key") == "value"


def test_context_memory_clear_session() -> None:
    """Test clearing session memory."""
    memory = ContextMemory()

    fact = EntityFact(uid="task-1", title="Task", entity_type="task")
    memory.add_entity_fact("session-1", fact)

    assert memory.has_context("session-1")

    memory.clear_session("session-1")

    assert not memory.has_context("session-1")


def test_context_memory_max_facts_limit() -> None:
    """Test that max facts limit is enforced."""
    memory = ContextMemory(max_facts=3)

    for i in range(5):
        fact = EntityFact(uid=f"task-{i}", title=f"Task {i}", entity_type="task")
        memory.add_entity_fact("session-1", fact)

    # Should only keep last 3
    session = memory.sessions["session-1"]
    assert len(session["facts"]) == 3


def test_context_memory_max_messages_limit() -> None:
    """Test that max messages limit is enforced."""
    memory = ContextMemory(max_messages=3)

    for i in range(5):
        memory.add_message("session-1", "user", f"Message {i}")

    session = memory.sessions["session-1"]
    assert len(session["messages"]) == 3


def test_create_context_memory_factory() -> None:
    """Test context memory factory function."""
    memory = create_context_memory(max_facts=15, max_messages=8)

    assert isinstance(memory, ContextMemory)
    assert memory.max_facts == 15
    assert memory.max_messages == 8


def test_context_memory_round_trip() -> None:
    """Test full round trip of memory serialization."""
    memory1 = ContextMemory()

    fact = EntityFact(uid="task-1", title="Task", entity_type="task", status="todo")
    memory1.add_entity_fact("session-1", fact)
    memory1.add_message("session-1", "user", "Create task")
    memory1.set_context("session-1", "flag", True)

    # Export
    data = memory1.to_dict("session-1")

    # Import to new memory
    memory2 = ContextMemory()
    memory2.from_dict("session-1", data)

    # Verify
    assert memory2.get_entity_by_uid("session-1", "task-1") is not None
    assert memory2.get_context("session-1", "flag") is True

