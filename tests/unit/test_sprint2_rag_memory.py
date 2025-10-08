"""Unit tests for RAG and memory components."""

from pathlib import Path

import pytest

from kira.agent.memory import ConversationMemory, ConversationTurn
from kira.agent.rag import Document, RAGStore, SearchResult


class TestRAGStore:
    """Tests for RAG store."""

    def test_add_and_search_documents(self, tmp_path):
        """Test adding and searching documents."""
        index_path = tmp_path / "test_index.json"
        rag = RAGStore(index_path)

        # Add documents
        doc1 = Document(
            id="doc1",
            content="How to create tasks in Kira",
            metadata={"type": "help"},
        )
        doc2 = Document(
            id="doc2",
            content="Understanding task status workflow",
            metadata={"type": "help"},
        )

        rag.add_document(doc1)
        rag.add_document(doc2)

        # Search
        results = rag.search("create task", top_k=2)

        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)

    def test_persistence(self, tmp_path):
        """Test index persistence."""
        index_path = tmp_path / "test_index.json"

        # Create and populate
        rag1 = RAGStore(index_path)
        doc = Document(id="test", content="Test content", metadata={})
        rag1.add_document(doc)

        # Load in new instance
        rag2 = RAGStore(index_path)
        results = rag2.search("test", top_k=1)

        assert len(results) > 0
        assert results[0].document.id == "test"

    def test_clear(self, tmp_path):
        """Test clearing index."""
        index_path = tmp_path / "test_index.json"
        rag = RAGStore(index_path)

        doc = Document(id="test", content="Test", metadata={})
        rag.add_document(doc)
        assert len(rag.documents) == 1

        rag.clear()
        assert len(rag.documents) == 0


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
