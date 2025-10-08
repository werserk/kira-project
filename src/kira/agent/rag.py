"""Retrieval-Augmented Generation (RAG) support for agent.

Provides document indexing and retrieval for context enhancement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "RAGStore",
    "Document",
    "SearchResult",
]


@dataclass
class Document:
    """Document for RAG indexing."""

    id: str
    content: str
    metadata: dict[str, Any]


@dataclass
class SearchResult:
    """Search result from RAG."""

    document: Document
    score: float


class RAGStore:
    """Simple RAG store using TF-IDF for Sprint 2.

    Note: This is a minimal implementation. Production would use FAISS or Chroma.
    """

    def __init__(self, index_path: Path) -> None:
        """Initialize RAG store.

        Parameters
        ----------
        index_path
            Path to store index
        """
        self.index_path = index_path
        self.documents: dict[str, Document] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load index from disk if it exists."""
        if self.index_path.exists():
            try:
                with self.index_path.open() as f:
                    data = json.load(f)
                    for doc_data in data:
                        doc = Document(
                            id=doc_data["id"],
                            content=doc_data["content"],
                            metadata=doc_data.get("metadata", {}),
                        )
                        self.documents[doc.id] = doc
            except Exception:
                # If index is corrupted, start fresh
                pass

    def _save_index(self) -> None:
        """Save index to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("w") as f:
            data = [
                {
                    "id": doc.id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                }
                for doc in self.documents.values()
            ]
            json.dump(data, f, indent=2)

    def add_document(self, document: Document) -> None:
        """Add document to index.

        Parameters
        ----------
        document
            Document to add
        """
        self.documents[document.id] = document
        self._save_index()

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """Search for relevant documents.

        Parameters
        ----------
        query
            Search query
        top_k
            Number of results to return

        Returns
        -------
        list[SearchResult]
            Top-K search results
        """
        # Simple keyword matching (TF-IDF would be better)
        query_terms = set(query.lower().split())
        results = []

        for doc in self.documents.values():
            doc_terms = set(doc.content.lower().split())
            # Calculate Jaccard similarity
            intersection = query_terms.intersection(doc_terms)
            union = query_terms.union(doc_terms)
            score = len(intersection) / len(union) if union else 0.0

            if score > 0:
                results.append(SearchResult(document=doc, score=score))

        # Sort by score and return top-K
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def clear(self) -> None:
        """Clear all documents from index."""
        self.documents.clear()
        self._save_index()


def build_rag_index(vault_path: Path, index_path: Path) -> RAGStore:
    """Build RAG index from vault documentation.

    Parameters
    ----------
    vault_path
        Path to vault
    index_path
        Path to store index

    Returns
    -------
    RAGStore
        Populated RAG store
    """
    rag = RAGStore(index_path)

    # Index README files
    readme_paths = [
        vault_path / "tasks" / "README.md",
        vault_path / "notes" / "README.md",
        vault_path / "inbox" / "README.md",
    ]

    for readme_path in readme_paths:
        if readme_path.exists():
            content = readme_path.read_text()
            doc = Document(
                id=str(readme_path.relative_to(vault_path)),
                content=content,
                metadata={"type": "readme", "path": str(readme_path)},
            )
            rag.add_document(doc)

    # Add tool documentation
    tool_docs = [
        Document(
            id="tool_task_create",
            content="Create new tasks with title, tags, due date, and assignee. Supports dry_run mode.",
            metadata={"type": "tool", "tool": "task_create"},
        ),
        Document(
            id="tool_task_update",
            content="Update existing tasks. Can change status (todo, doing, done), assignee, title. FSM guards apply.",
            metadata={"type": "tool", "tool": "task_update"},
        ),
        Document(
            id="tool_task_list",
            content="List tasks with optional filters by status and tags. Returns JSON array.",
            metadata={"type": "tool", "tool": "task_list"},
        ),
        Document(
            id="tool_rollup_daily",
            content="Generate daily rollup report for a given date and timezone.",
            metadata={"type": "tool", "tool": "rollup_daily"},
        ),
    ]

    for doc in tool_docs:
        rag.add_document(doc)

    return rag
