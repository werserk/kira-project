"""Tests for persistent conversation memory."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from kira.adapters.llm import Message
from kira.agent.persistent_memory import (ConversationTurn,
                                          PersistentConversationMemory)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "test_conversations.db"


@pytest.fixture
def memory(temp_db: Path) -> PersistentConversationMemory:
    """Create fresh memory instance."""
    return PersistentConversationMemory(db_path=temp_db, max_exchanges=5)


def test_initialization(temp_db: Path):
    """Test memory initialization and database creation."""
    memory = PersistentConversationMemory(db_path=temp_db, max_exchanges=10)

    # Database should be created
    assert temp_db.exists()

    # Tables should exist
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
        )
        assert cursor.fetchone() is not None


def test_add_turn(memory: PersistentConversationMemory):
    """Test adding conversation turn."""
    memory.add_turn(
        "user123",
        user_message="Hello",
        assistant_message="Hi there!",
        metadata={"test": "value"},
    )

    # Check database
    with sqlite3.connect(memory.db_path) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE session_id = ?", ("user123",)
        )
        # Should have 2 messages (user + assistant)
        assert cursor.fetchone()[0] == 2


def test_get_context_messages(memory: PersistentConversationMemory):
    """Test retrieving context messages."""
    # Add some turns
    memory.add_turn("session1", "Question 1", "Answer 1")
    memory.add_turn("session1", "Question 2", "Answer 2")
    memory.add_turn("session1", "Question 3", "Answer 3")

    # Get messages
    messages = memory.get_context_messages("session1")

    # Should have 6 messages (3 exchanges * 2 messages)
    assert len(messages) == 6

    # Check order
    assert messages[0].role == "user"
    assert messages[0].content == "Question 1"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Answer 1"
    assert messages[4].role == "user"
    assert messages[4].content == "Question 3"


def test_get_context_messages_with_limit(memory: PersistentConversationMemory):
    """Test retrieving limited context messages."""
    # Add some turns
    for i in range(10):
        memory.add_turn("session1", f"Question {i}", f"Answer {i}")

    # Get only last 2 exchanges
    messages = memory.get_context_messages("session1", limit=2)

    # Should have 4 messages (2 exchanges * 2 messages)
    assert len(messages) == 4
    assert messages[0].content == "Question 8"


def test_get_turns(memory: PersistentConversationMemory):
    """Test retrieving conversation turns."""
    # Add turns
    memory.add_turn("session1", "Q1", "A1", metadata={"turn": 1})
    memory.add_turn("session1", "Q2", "A2", metadata={"turn": 2})

    # Get turns
    turns = memory.get_turns("session1")

    assert len(turns) == 2
    assert isinstance(turns[0], ConversationTurn)
    assert turns[0].user_message == "Q1"
    assert turns[0].assistant_message == "A1"
    assert turns[0].metadata["turn"] == 1


def test_clear_session(memory: PersistentConversationMemory):
    """Test clearing session memory."""
    # Add turns to multiple sessions
    memory.add_turn("session1", "Q1", "A1")
    memory.add_turn("session2", "Q2", "A2")

    # Clear session1
    memory.clear_session("session1")

    # Session1 should be empty
    assert not memory.has_context("session1")

    # Session2 should still have data
    assert memory.has_context("session2")


def test_has_context(memory: PersistentConversationMemory):
    """Test checking if session has context."""
    # Empty session
    assert not memory.has_context("empty_session")

    # Add turn
    memory.add_turn("session1", "Q", "A")

    # Should have context now
    assert memory.has_context("session1")


def test_persistence_across_instances(temp_db: Path):
    """Test that memory persists across instances."""
    # Create first instance and add data
    memory1 = PersistentConversationMemory(db_path=temp_db, max_exchanges=5)
    memory1.add_turn("session1", "Question", "Answer")

    # Create second instance
    memory2 = PersistentConversationMemory(db_path=temp_db, max_exchanges=5)

    # Should be able to retrieve data
    messages = memory2.get_context_messages("session1")
    assert len(messages) == 2
    assert messages[0].content == "Question"


def test_cleanup_old_messages(temp_db: Path):
    """Test automatic cleanup of old messages."""
    # Create memory with small limit
    memory = PersistentConversationMemory(db_path=temp_db, max_exchanges=3)

    # Add more than max_exchanges
    for i in range(5):
        memory.add_turn("session1", f"Q{i}", f"A{i}")

    # Should only keep last 3 exchanges
    turns = memory.get_turns("session1")
    assert len(turns) == 3

    # Should be the most recent ones
    assert turns[0].user_message == "Q2"
    assert turns[-1].user_message == "Q4"


def test_multiple_sessions(memory: PersistentConversationMemory):
    """Test handling multiple sessions."""
    # Add turns to different sessions
    memory.add_turn("user1", "Hello", "Hi")
    memory.add_turn("user2", "Bonjour", "Salut")
    memory.add_turn("user1", "How are you?", "I'm good")

    # Each session should have its own context
    user1_messages = memory.get_context_messages("user1")
    user2_messages = memory.get_context_messages("user2")

    assert len(user1_messages) == 4  # 2 exchanges
    assert len(user2_messages) == 2  # 1 exchange

    # Messages should not mix
    assert "Bonjour" not in [msg.content for msg in user1_messages]


def test_get_session_count(memory: PersistentConversationMemory):
    """Test getting session count."""
    assert memory.get_session_count() == 0

    memory.add_turn("session1", "Q", "A")
    assert memory.get_session_count() == 1

    memory.add_turn("session2", "Q", "A")
    assert memory.get_session_count() == 2

    # Adding to same session shouldn't increase count
    memory.add_turn("session1", "Q2", "A2")
    assert memory.get_session_count() == 2


def test_get_all_sessions(memory: PersistentConversationMemory):
    """Test getting all session IDs."""
    # Add turns to different sessions
    memory.add_turn("telegram:123", "Q", "A")
    memory.add_turn("telegram:456", "Q", "A")
    memory.add_turn("cli:default", "Q", "A")

    sessions = memory.get_all_sessions()
    assert len(sessions) == 3
    assert "telegram:123" in sessions
    assert "telegram:456" in sessions
    assert "cli:default" in sessions


def test_export_session(memory: PersistentConversationMemory):
    """Test exporting session data."""
    # Add some turns
    memory.add_turn("session1", "Q1", "A1", metadata={"test": "value"})
    memory.add_turn("session1", "Q2", "A2")

    # Export
    export = memory.export_session("session1")

    assert export["session_id"] == "session1"
    assert export["turn_count"] == 2
    assert len(export["turns"]) == 2
    assert export["turns"][0]["user_message"] == "Q1"
    assert export["turns"][0]["metadata"]["test"] == "value"


def test_cache_functionality(memory: PersistentConversationMemory):
    """Test that cache works correctly."""
    # Add turns
    memory.add_turn("session1", "Q1", "A1")
    memory.add_turn("session1", "Q2", "A2")

    # First retrieval (from DB)
    messages1 = memory.get_context_messages("session1")

    # Second retrieval (should use cache)
    messages2 = memory.get_context_messages("session1")

    # Should get same results
    assert len(messages1) == len(messages2)
    assert messages1[0].content == messages2[0].content


def test_conversation_turn_serialization():
    """Test ConversationTurn serialization."""
    turn = ConversationTurn(
        user_message="Hello",
        assistant_message="Hi",
        timestamp=123.456,
        metadata={"key": "value"},
    )

    # Serialize
    data = turn.to_dict()
    assert data["user_message"] == "Hello"
    assert data["assistant_message"] == "Hi"
    assert data["timestamp"] == 123.456
    assert data["metadata"]["key"] == "value"

    # Deserialize
    restored = ConversationTurn.from_dict(data)
    assert restored.user_message == turn.user_message
    assert restored.assistant_message == turn.assistant_message
    assert restored.timestamp == turn.timestamp
    assert restored.metadata == turn.metadata


def test_timestamp_ordering(memory: PersistentConversationMemory):
    """Test that messages are returned in timestamp order."""
    # Add turns with slight delays
    memory.add_turn("session1", "First", "Response 1")
    time.sleep(0.01)
    memory.add_turn("session1", "Second", "Response 2")
    time.sleep(0.01)
    memory.add_turn("session1", "Third", "Response 3")

    # Get messages
    messages = memory.get_context_messages("session1")

    # Should be in chronological order
    assert messages[0].content == "First"
    assert messages[2].content == "Second"
    assert messages[4].content == "Third"


def test_empty_session(memory: PersistentConversationMemory):
    """Test retrieving from empty session."""
    messages = memory.get_context_messages("nonexistent")
    assert len(messages) == 0

    turns = memory.get_turns("nonexistent")
    assert len(turns) == 0


def test_message_type_conversion(memory: PersistentConversationMemory):
    """Test that returned messages are correct type."""
    memory.add_turn("session1", "Question", "Answer")

    messages = memory.get_context_messages("session1")

    for msg in messages:
        assert isinstance(msg, Message)
        assert hasattr(msg, "role")
        assert hasattr(msg, "content")
        assert msg.role in ("user", "assistant")


def test_concurrent_sessions(memory: PersistentConversationMemory):
    """Test adding to multiple sessions concurrently."""
    # Simulate multiple users
    for i in range(10):
        session_id = f"user{i % 3}"  # 3 different users
        memory.add_turn(session_id, f"Message {i}", f"Response {i}")

    # Each user should have their own history
    user0_messages = memory.get_context_messages("user0")
    user1_messages = memory.get_context_messages("user1")
    user2_messages = memory.get_context_messages("user2")

    # Each should have roughly equal messages
    assert len(user0_messages) > 0
    assert len(user1_messages) > 0
    assert len(user2_messages) > 0

    # Total messages
    total = len(user0_messages) + len(user1_messages) + len(user2_messages)
    assert total == 20  # 10 exchanges * 2 messages each

