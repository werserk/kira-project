"""Enhanced context memory for LangGraph agent.

Phase 2, Item 8: Ephemeral memory & short-term context.
Stores compact facts and entity references for multi-turn flows.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ContextMemory", "EntityFact", "create_context_memory"]


@dataclass
class EntityFact:
    """Compact fact about an entity."""

    uid: str
    title: str
    entity_type: str
    status: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "uid": self.uid,
            "title": self.title,
            "type": self.entity_type,
        }
        if self.status:
            result["status"] = self.status
        if self.tags:
            result["tags"] = self.tags
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityFact:
        """Create from dictionary."""
        return cls(
            uid=data["uid"],
            title=data["title"],
            entity_type=data.get("type", "unknown"),
            status=data.get("status"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


class ContextMemory:
    """Ephemeral context memory for agent state.

    Stores:
    - Recent entity facts (uid, title, status)
    - Last N user messages
    - Operation results
    - Session-specific context

    Enables multi-turn flows where agent remembers entities
    without re-querying (e.g., "update that task").
    """

    def __init__(self, max_facts: int = 20, max_messages: int = 10) -> None:
        """Initialize context memory.

        Parameters
        ----------
        max_facts
            Maximum entity facts to store
        max_messages
            Maximum message history to store
        """
        self.max_facts = max_facts
        self.max_messages = max_messages
        self.sessions: dict[str, dict[str, Any]] = {}

    def _get_session(self, session_id: str) -> dict[str, Any]:
        """Get or create session data.

        Parameters
        ----------
        session_id
            Session identifier

        Returns
        -------
        dict
            Session data
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "facts": deque(maxlen=self.max_facts),
                "messages": deque(maxlen=self.max_messages),
                "last_entities": {},  # uid -> EntityFact
                "context": {},  # Free-form context
            }
        return self.sessions[session_id]

    def add_entity_fact(self, session_id: str, fact: EntityFact) -> None:
        """Add entity fact to memory.

        Parameters
        ----------
        session_id
            Session identifier
        fact
            Entity fact
        """
        session = self._get_session(session_id)
        session["facts"].append(fact)
        session["last_entities"][fact.uid] = fact

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add message to history.

        Parameters
        ----------
        session_id
            Session identifier
        role
            Message role (user/assistant)
        content
            Message content
        """
        session = self._get_session(session_id)
        session["messages"].append({"role": role, "content": content})

    def get_last_entity(self, session_id: str, entity_type: str | None = None) -> EntityFact | None:
        """Get last referenced entity.

        Parameters
        ----------
        session_id
            Session identifier
        entity_type
            Optional entity type filter

        Returns
        -------
        EntityFact | None
            Last entity or None
        """
        session = self._get_session(session_id)
        facts = list(session["facts"])

        # Search backwards
        for fact in reversed(facts):
            if entity_type is None or fact.entity_type == entity_type:
                return fact

        return None

    def get_entity_by_uid(self, session_id: str, uid: str) -> EntityFact | None:
        """Get entity by UID.

        Parameters
        ----------
        session_id
            Session identifier
        uid
            Entity UID

        Returns
        -------
        EntityFact | None
            Entity or None
        """
        session = self._get_session(session_id)
        return session["last_entities"].get(uid)

    def set_context(self, session_id: str, key: str, value: Any) -> None:
        """Set session context value.

        Parameters
        ----------
        session_id
            Session identifier
        key
            Context key
        value
            Context value
        """
        session = self._get_session(session_id)
        session["context"][key] = value

    def get_context(self, session_id: str, key: str, default: Any = None) -> Any:
        """Get session context value.

        Parameters
        ----------
        session_id
            Session identifier
        key
            Context key
        default
            Default value if not found

        Returns
        -------
        Any
            Context value or default
        """
        session = self._get_session(session_id)
        return session["context"].get(key, default)

    def get_facts_summary(self, session_id: str, limit: int = 5) -> str:
        """Get summary of recent facts.

        Parameters
        ----------
        session_id
            Session identifier
        limit
            Maximum facts to include

        Returns
        -------
        str
            Formatted summary
        """
        session = self._get_session(session_id)
        facts = list(session["facts"])[-limit:]

        if not facts:
            return "No recent entities."

        lines = ["Recent entities:"]
        for fact in facts:
            status_str = f" ({fact.status})" if fact.status else ""
            lines.append(f"- {fact.uid}: {fact.title}{status_str}")

        return "\n".join(lines)

    def to_dict(self, session_id: str) -> dict[str, Any]:
        """Export session memory to dictionary.

        Parameters
        ----------
        session_id
            Session identifier

        Returns
        -------
        dict
            Session memory data
        """
        session = self._get_session(session_id)
        return {
            "facts": [f.to_dict() for f in session["facts"]],
            "messages": list(session["messages"]),
            "context": session["context"],
        }

    def from_dict(self, session_id: str, data: dict[str, Any]) -> None:
        """Import session memory from dictionary.

        Parameters
        ----------
        session_id
            Session identifier
        data
            Session memory data
        """
        session = self._get_session(session_id)

        # Load facts
        for fact_data in data.get("facts", []):
            fact = EntityFact.from_dict(fact_data)
            session["facts"].append(fact)
            session["last_entities"][fact.uid] = fact

        # Load messages
        for msg in data.get("messages", []):
            session["messages"].append(msg)

        # Load context
        session["context"].update(data.get("context", {}))

    def clear_session(self, session_id: str) -> None:
        """Clear session memory.

        Parameters
        ----------
        session_id
            Session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]

    def has_context(self, session_id: str) -> bool:
        """Check if session has any context.

        Parameters
        ----------
        session_id
            Session identifier

        Returns
        -------
        bool
            True if session has facts or messages
        """
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        return len(session["facts"]) > 0 or len(session["messages"]) > 0


def create_context_memory(max_facts: int = 20, max_messages: int = 10) -> ContextMemory:
    """Factory function to create context memory.

    Parameters
    ----------
    max_facts
        Maximum entity facts to store
    max_messages
        Maximum message history to store

    Returns
    -------
    ContextMemory
        Configured context memory
    """
    return ContextMemory(max_facts, max_messages)

