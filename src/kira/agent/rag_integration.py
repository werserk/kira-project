"""RAG integration for LangGraph agent.

Phase 2, Item 9: RAG mini hook (optional but recommended).
Provides pre-planning retrieval over docs, tool schemas, and examples.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .rag import RAGStore

from .rag import Document, build_rag_index
from .tool_schemas import TOOL_SCHEMAS

logger = logging.getLogger(__name__)

__all__ = ["RAGIntegration", "create_rag_integration", "enhance_prompt_with_rag"]


class RAGIntegration:
    """RAG integration for agent planning.

    Enhances planning with:
    - Tool documentation and schemas
    - Usage examples
    - FSM state transition rules
    - Best practices
    """

    def __init__(self, rag_store: RAGStore | None = None, enable_rag: bool = True) -> None:
        """Initialize RAG integration.

        Parameters
        ----------
        rag_store
            Optional RAG store (if None, RAG is disabled)
        enable_rag
            Enable/disable RAG retrieval
        """
        self.rag_store = rag_store
        self.enable_rag = enable_rag and rag_store is not None

    def retrieve_context(self, query: str, top_k: int = 3) -> list[str]:
        """Retrieve relevant context for query.

        Parameters
        ----------
        query
            User query
        top_k
            Number of results to retrieve

        Returns
        -------
        list[str]
            Context snippets
        """
        if not self.enable_rag or not self.rag_store:
            return []

        try:
            results = self.rag_store.search(query, top_k=top_k)
            snippets = []

            for result in results:
                # Format snippet with metadata
                doc = result.document
                doc_type = doc.metadata.get("type", "doc")

                if doc_type == "tool":
                    tool_name = doc.metadata.get("tool", "")
                    snippet = f"Tool '{tool_name}': {doc.content[:200]}"
                else:
                    snippet = doc.content[:200]

                snippets.append(snippet)

            logger.info(f"Retrieved {len(snippets)} context snippets for query")
            return snippets

        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}", exc_info=True)
            return []

    def get_tool_examples(self, tool_name: str) -> str:
        """Get usage examples for a tool.

        Parameters
        ----------
        tool_name
            Tool name

        Returns
        -------
        str
            Usage examples
        """
        examples = {
            "task_create": """Example:
{"tool": "task_create", "args": {"title": "Review PR", "tags": ["dev"]}, "dry_run": true}""",
            "task_update": """Example:
{"tool": "task_update", "args": {"uid": "task-123", "status": "done"}, "dry_run": false}""",
            "task_list": """Example:
{"tool": "task_list", "args": {"status": "todo", "limit": 10}, "dry_run": false}""",
            "rollup_daily": """Example:
{"tool": "rollup_daily", "args": {"date_local": "2025-01-15", "timezone": "UTC"}, "dry_run": false}""",
        }

        return examples.get(tool_name, "")

    def enhance_system_prompt(self, base_prompt: str, query: str) -> str:
        """Enhance system prompt with RAG context.

        Parameters
        ----------
        base_prompt
            Base system prompt
        query
            User query

        Returns
        -------
        str
            Enhanced prompt
        """
        if not self.enable_rag:
            return base_prompt

        # Retrieve relevant context
        snippets = self.retrieve_context(query, top_k=3)

        if not snippets:
            return base_prompt

        # Build context section
        context_section = "\n\nRELEVANT CONTEXT:\n"
        for i, snippet in enumerate(snippets, 1):
            context_section += f"{i}. {snippet}\n"

        return base_prompt + context_section


def enhance_prompt_with_rag(
    base_prompt: str,
    query: str,
    rag_store: RAGStore | None = None,
    top_k: int = 3,
) -> str:
    """Utility function to enhance prompt with RAG context.

    Parameters
    ----------
    base_prompt
        Base system prompt
    query
        User query
    rag_store
        Optional RAG store
    top_k
        Number of context snippets to retrieve

    Returns
    -------
    str
        Enhanced prompt with RAG context
    """
    if not rag_store:
        return base_prompt

    integration = RAGIntegration(rag_store, enable_rag=True)
    return integration.enhance_system_prompt(base_prompt, query)


def create_rag_integration(
    vault_path: Path | None = None,
    index_path: Path | None = None,
    enable_rag: bool = True,
) -> RAGIntegration:
    """Factory function to create RAG integration.

    Parameters
    ----------
    vault_path
        Path to vault (for building index)
    index_path
        Path to store index
    enable_rag
        Enable/disable RAG

    Returns
    -------
    RAGIntegration
        Configured RAG integration
    """
    if not enable_rag or not vault_path or not index_path:
        logger.info("RAG integration disabled")
        return RAGIntegration(rag_store=None, enable_rag=False)

    try:
        # Build or load index
        rag_store = build_rag_index(vault_path, index_path)

        # Add tool schemas to index
        for tool_name, schema in TOOL_SCHEMAS.items():
            doc = Document(
                id=f"schema_{tool_name}",
                content=f"{tool_name}: {schema.description}. Schema: {schema.get_json_schema()}",
                metadata={"type": "schema", "tool": tool_name},
            )
            rag_store.add_document(doc)

        logger.info(f"RAG integration enabled with {len(rag_store.documents)} documents")
        return RAGIntegration(rag_store, enable_rag=True)

    except Exception as e:
        logger.error(f"Failed to initialize RAG: {e}", exc_info=True)
        return RAGIntegration(rag_store=None, enable_rag=False)

