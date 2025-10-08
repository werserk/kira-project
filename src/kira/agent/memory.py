"""Conversation memory for agent.

Maintains ephemeral dialogue context across requests.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..adapters.llm import Message

__all__ = ["ConversationMemory", "ConversationTurn"]


@dataclass
class ConversationTurn:
    """Single conversation turn."""

    user_message: str
    assistant_message: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationMemory:
    """Ephemeral conversation memory.

    Stores limited dialogue history per session.
    """

    def __init__(self, max_exchanges: int = 3) -> None:
        """Initialize conversation memory.

        Parameters
        ----------
        max_exchanges
            Maximum number of exchanges to remember
        """
        self.max_exchanges = max_exchanges
        self.sessions: dict[str, deque[ConversationTurn]] = {}

    def add_turn(self, trace_id: str, user_message: str, assistant_message: str, metadata: dict[str, Any] | None = None) -> None:
        """Add conversation turn to memory.

        Parameters
        ----------
        trace_id
            Session/trace identifier
        user_message
            User's message
        assistant_message
            Assistant's response
        metadata
            Optional metadata
        """
        if trace_id not in self.sessions:
            self.sessions[trace_id] = deque(maxlen=self.max_exchanges)

        turn = ConversationTurn(
            user_message=user_message,
            assistant_message=assistant_message,
            metadata=metadata or {},
        )

        self.sessions[trace_id].append(turn)

    def get_context_messages(self, trace_id: str) -> list[Message]:
        """Get context messages for session.

        Parameters
        ----------
        trace_id
            Session/trace identifier

        Returns
        -------
        list[Message]
            Context messages in chronological order
        """
        if trace_id not in self.sessions:
            return []

        messages = []
        for turn in self.sessions[trace_id]:
            messages.append(Message(role="user", content=turn.user_message))
            messages.append(Message(role="assistant", content=turn.assistant_message))

        return messages

    def clear_session(self, trace_id: str) -> None:
        """Clear session memory.

        Parameters
        ----------
        trace_id
            Session/trace identifier
        """
        if trace_id in self.sessions:
            del self.sessions[trace_id]

    def has_context(self, trace_id: str) -> bool:
        """Check if session has context.

        Parameters
        ----------
        trace_id
            Session/trace identifier

        Returns
        -------
        bool
            True if session has context
        """
        return trace_id in self.sessions and len(self.sessions[trace_id]) > 0
