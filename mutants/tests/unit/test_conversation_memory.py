"""Unit tests for conversation memory management."""

import pytest

from kira.agent.memory import ConversationMemory, ConversationTurn


class TestConversationMemory:
    """Tests for conversation memory."""

    def test_add_turn(self):
        """Test adding conversation turn."""
        memory = ConversationMemory(max_exchanges=3)

        memory.add_turn("trace1", "Hello", "Hi there")

        assert memory.has_context("trace1")
        messages = memory.get_context_messages("trace1")
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there"

    def test_max_exchanges_limit(self):
        """Test max exchanges limit."""
        memory = ConversationMemory(max_exchanges=2)

        memory.add_turn("trace1", "First", "Response1")
        memory.add_turn("trace1", "Second", "Response2")
        memory.add_turn("trace1", "Third", "Response3")

        messages = memory.get_context_messages("trace1")

        # Should only have last 2 exchanges (4 messages)
        assert len(messages) == 4
        assert "Second" in messages[0].content

    def test_clear_session(self):
        """Test clearing session."""
        memory = ConversationMemory()

        memory.add_turn("trace1", "Test", "Response")
        assert memory.has_context("trace1")

        memory.clear_session("trace1")
        assert not memory.has_context("trace1")

    def test_separate_sessions(self):
        """Test separate session isolation."""
        memory = ConversationMemory()

        memory.add_turn("trace1", "Message1", "Response1")
        memory.add_turn("trace2", "Message2", "Response2")

        assert memory.has_context("trace1")
        assert memory.has_context("trace2")

        messages1 = memory.get_context_messages("trace1")
        messages2 = memory.get_context_messages("trace2")

        assert messages1[0].content == "Message1"
        assert messages2[0].content == "Message2"

    def test_empty_memory(self):
        """Test behavior with no stored context."""
        memory = ConversationMemory()

        assert not memory.has_context("nonexistent")
        messages = memory.get_context_messages("nonexistent")
        assert len(messages) == 0

    def test_multiple_turns_same_session(self):
        """Test multiple conversation turns in same session."""
        memory = ConversationMemory(max_exchanges=5)

        memory.add_turn("session1", "Question 1", "Answer 1")
        memory.add_turn("session1", "Question 2", "Answer 2")
        memory.add_turn("session1", "Question 3", "Answer 3")

        messages = memory.get_context_messages("session1")

        # Should have 6 messages (3 exchanges)
        assert len(messages) == 6
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    def test_context_overflow(self):
        """Test that oldest exchanges are dropped when limit exceeded."""
        memory = ConversationMemory(max_exchanges=2)

        memory.add_turn("trace1", "First question", "First answer")
        memory.add_turn("trace1", "Second question", "Second answer")
        memory.add_turn("trace1", "Third question", "Third answer")

        messages = memory.get_context_messages("trace1")

        # Should only have 2 most recent exchanges
        assert len(messages) == 4
        assert "First" not in messages[0].content
        assert "Second" in messages[0].content or "Third" in messages[0].content
