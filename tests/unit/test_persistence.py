"""Unit tests for agent state persistence."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kira.agent.persistence import (
    FileStatePersistence,
    SQLiteStatePersistence,
    create_persistence,
)
from kira.agent.state import AgentState, Budget


def test_file_persistence_save_load() -> None:
    """Test file persistence save and load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)
        persistence = FileStatePersistence(storage_path)

        state = AgentState(
            trace_id="test-123",
            user="alice",
            messages=[{"role": "user", "content": "Test"}],
        )

        # Save
        persistence.save_state("test-123", state)

        # Load
        loaded_data = persistence.load_state("test-123")

        assert loaded_data is not None
        assert loaded_data["trace_id"] == "test-123"
        assert loaded_data["user"] == "alice"


def test_file_persistence_load_nonexistent() -> None:
    """Test loading nonexistent state returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)
        persistence = FileStatePersistence(storage_path)

        loaded = persistence.load_state("nonexistent")

        assert loaded is None


def test_file_persistence_delete() -> None:
    """Test deleting saved state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)
        persistence = FileStatePersistence(storage_path)

        state = AgentState(trace_id="test-456")

        # Save and verify
        persistence.save_state("test-456", state)
        assert persistence.load_state("test-456") is not None

        # Delete and verify
        persistence.delete_state("test-456")
        assert persistence.load_state("test-456") is None


def test_file_persistence_list_states() -> None:
    """Test listing all saved states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)
        persistence = FileStatePersistence(storage_path)

        state1 = AgentState(trace_id="trace-1")
        state2 = AgentState(trace_id="trace-2")

        persistence.save_state("trace-1", state1)
        persistence.save_state("trace-2", state2)

        states = persistence.list_states()

        assert len(states) == 2
        assert "trace-1" in states
        assert "trace-2" in states


def test_file_persistence_sanitize_trace_id() -> None:
    """Test that trace IDs are sanitized for filesystem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)
        persistence = FileStatePersistence(storage_path)

        state = AgentState(trace_id="trace/with/slashes")

        # Should not raise
        persistence.save_state("trace/with/slashes", state)

        # Should be able to load
        loaded = persistence.load_state("trace/with/slashes")
        assert loaded is not None


def test_sqlite_persistence_save_load() -> None:
    """Test SQLite persistence save and load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        persistence = SQLiteStatePersistence(db_path)

        state = AgentState(
            trace_id="test-789",
            user="bob",
            status="completed",
        )

        # Save
        persistence.save_state("test-789", state)

        # Load
        loaded_data = persistence.load_state("test-789")

        assert loaded_data is not None
        assert loaded_data["trace_id"] == "test-789"
        assert loaded_data["user"] == "bob"
        assert loaded_data["status"] == "completed"


def test_sqlite_persistence_update() -> None:
    """Test updating existing state in SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        persistence = SQLiteStatePersistence(db_path)

        state1 = AgentState(trace_id="test-update", status="pending")
        persistence.save_state("test-update", state1)

        state2 = AgentState(trace_id="test-update", status="completed")
        persistence.save_state("test-update", state2)

        # Should have latest version
        loaded = persistence.load_state("test-update")
        assert loaded is not None
        assert loaded["status"] == "completed"


def test_sqlite_persistence_delete() -> None:
    """Test deleting state from SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        persistence = SQLiteStatePersistence(db_path)

        state = AgentState(trace_id="test-delete")

        persistence.save_state("test-delete", state)
        assert persistence.load_state("test-delete") is not None

        persistence.delete_state("test-delete")
        assert persistence.load_state("test-delete") is None


def test_sqlite_persistence_list_states() -> None:
    """Test listing states from SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        persistence = SQLiteStatePersistence(db_path)

        state1 = AgentState(trace_id="trace-a")
        state2 = AgentState(trace_id="trace-b")
        state3 = AgentState(trace_id="trace-c")

        persistence.save_state("trace-a", state1)
        persistence.save_state("trace-b", state2)
        persistence.save_state("trace-c", state3)

        states = persistence.list_states()

        assert len(states) == 3
        assert "trace-a" in states
        assert "trace-b" in states
        assert "trace-c" in states


def test_sqlite_persistence_complex_state() -> None:
    """Test persisting complex state with nested data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        persistence = SQLiteStatePersistence(db_path)

        state = AgentState(
            trace_id="complex-123",
            user="charlie",
            messages=[
                {"role": "user", "content": "Message 1"},
                {"role": "assistant", "content": "Response 1"},
            ],
            plan=[
                {"tool": "task_create", "args": {"title": "Task"}},
            ],
            tool_results=[
                {"status": "ok", "data": {"uid": "task-1"}},
            ],
            memory={"last_action": "create", "count": 5},
        )
        state.budget.steps_used = 2
        state.budget.tokens_used = 500

        # Save and load
        persistence.save_state("complex-123", state)
        loaded = persistence.load_state("complex-123")

        assert loaded is not None
        assert len(loaded["messages"]) == 2
        assert len(loaded["plan"]) == 1
        assert len(loaded["tool_results"]) == 1
        assert loaded["memory"]["count"] == 5
        assert loaded["budget"]["steps_used"] == 2


def test_create_persistence_file() -> None:
    """Test factory function creates file persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)

        persistence = create_persistence("file", storage_path)

        assert isinstance(persistence, FileStatePersistence)


def test_create_persistence_sqlite() -> None:
    """Test factory function creates SQLite persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)

        persistence = create_persistence("sqlite", storage_path)

        assert isinstance(persistence, SQLiteStatePersistence)


def test_create_persistence_default() -> None:
    """Test factory function with defaults."""
    persistence = create_persistence()

    assert isinstance(persistence, FileStatePersistence)


def test_persistence_state_round_trip() -> None:
    """Test full round trip: state -> save -> load -> recreate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)
        persistence = FileStatePersistence(storage_path)

        # Create state
        original = AgentState(
            trace_id="round-trip",
            user="dave",
            messages=[{"role": "user", "content": "Test message"}],
            status="executing",
        )
        original.budget = Budget(max_steps=5, steps_used=2)

        # Save
        persistence.save_state("round-trip", original)

        # Load
        loaded_data = persistence.load_state("round-trip")
        assert loaded_data is not None

        # Recreate state
        restored = AgentState.from_dict(loaded_data)

        # Verify
        assert restored.trace_id == original.trace_id
        assert restored.user == original.user
        assert restored.status == original.status
        assert len(restored.messages) == len(original.messages)
        assert restored.budget.steps_used == original.budget.steps_used

