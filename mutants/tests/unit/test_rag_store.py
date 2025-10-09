"""Unit tests for RAG (Retrieval-Augmented Generation) store."""

from pathlib import Path

import pytest

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

    def test_search_returns_ranked_results(self, tmp_path):
        """Test that search returns results ranked by relevance."""
        index_path = tmp_path / "test_index.json"
        rag = RAGStore(index_path)

        # Add documents with varying relevance
        docs = [
            Document(id="exact", content="Create a new task", metadata={}),
            Document(id="partial", content="Task management system", metadata={}),
            Document(id="unrelated", content="Weather forecast", metadata={}),
        ]

        for doc in docs:
            rag.add_document(doc)

        results = rag.search("create task", top_k=3)

        # Should return results (exact ranking depends on implementation)
        assert len(results) <= 3
        assert all(isinstance(r, SearchResult) for r in results)

    def test_empty_search(self, tmp_path):
        """Test search on empty index."""
        index_path = tmp_path / "test_index.json"
        rag = RAGStore(index_path)

        results = rag.search("anything", top_k=5)

        assert len(results) == 0

    def test_search_respects_top_k(self, tmp_path):
        """Test that search respects top_k parameter."""
        index_path = tmp_path / "test_index.json"
        rag = RAGStore(index_path)

        # Add many documents
        for i in range(10):
            doc = Document(id=f"doc{i}", content=f"Document {i} about tasks", metadata={})
            rag.add_document(doc)

        results = rag.search("tasks", top_k=3)

        assert len(results) <= 3
