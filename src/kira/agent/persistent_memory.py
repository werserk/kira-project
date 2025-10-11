"""Persistent conversation memory with SQLite storage.

This module provides conversation memory that survives agent restarts.
Conversations are stored in SQLite database and cached in memory for performance.
"""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..adapters.llm import Message

__all__ = ["PersistentConversationMemory", "ConversationTurn"]


@dataclass
class ConversationTurn:
    """Single conversation turn with metadata."""

    user_message: str
    assistant_message: str
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationTurn:
        """Create from dictionary."""
        return cls(
            user_message=data["user_message"],
            assistant_message=data["assistant_message"],
            timestamp=data.get("timestamp", 0.0),
            metadata=data.get("metadata", {}),
        )


class PersistentConversationMemory:
    """Conversation memory with SQLite persistence.

    Features:
    - Persistent storage across restarts
    - In-memory caching for performance
    - Per-session conversation history
    - Automatic cleanup of old conversations
    - Thread-safe operations

    Example
    -------
    >>> memory = PersistentConversationMemory(
    ...     db_path=Path("artifacts/conversations.db"),
    ...     max_exchanges=50
    ... )
    >>> memory.add_turn("user123", "Hello", "Hi there!")
    >>> messages = memory.get_context_messages("user123")
    """

    def __init__(
        self,
        db_path: Path,
        max_exchanges: int = 50,
        cache_size: int = 10,
    ) -> None:
        """Initialize persistent conversation memory.

        Parameters
        ----------
        db_path
            Path to SQLite database file
        max_exchanges
            Maximum number of exchanges to keep per session
        cache_size
            Number of recent exchanges to keep in memory cache
        """
        import logging
        logger = logging.getLogger(__name__)

        self.db_path = db_path
        self.max_exchanges = max_exchanges
        self.cache_size = min(cache_size, max_exchanges)

        # In-memory cache: session_id -> deque of recent turns
        self._cache: dict[str, deque[ConversationTurn]] = {}

        logger.info(
            f"🔍 DEBUG: PersistentConversationMemory init - "
            f"db_path={db_path}, max_exchanges={max_exchanges}, cache_size={cache_size}"
        )

        # Initialize database
        self._init_db()

        logger.info(f"✅ PersistentConversationMemory initialized at {db_path}")

    def _init_db(self) -> None:
        """Initialize database schema."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Index for fast session lookups
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_timestamp
                ON conversations(session_id, timestamp DESC)
                """
            )

            # Session state table for confirmation flow
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_state (
                    session_id TEXT PRIMARY KEY,
                    pending_confirmation INTEGER NOT NULL DEFAULT 0,
                    pending_plan TEXT,
                    confirmation_question TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.commit()

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add conversation turn to memory.

        Parameters
        ----------
        session_id
            Session identifier (e.g., "telegram:123456")
        user_message
            User's message
        assistant_message
            Assistant's response
        metadata
            Optional metadata
        """
        import logging
        import time

        logger = logging.getLogger(__name__)
        logger.info(
            f"🔍 DEBUG: PersistentMemory.add_turn() - session_id={session_id}, "
            f"user_len={len(user_message)}, assistant_len={len(assistant_message)}"
        )

        timestamp = time.time()
        turn = ConversationTurn(
            user_message=user_message,
            assistant_message=assistant_message,
            timestamp=timestamp,
            metadata=metadata or {},
        )

        # Add to cache
        if session_id not in self._cache:
            self._cache[session_id] = deque(maxlen=self.cache_size)
            logger.info(f"🔍 DEBUG: Created new cache for session {session_id}")
        self._cache[session_id].append(turn)
        logger.info(f"🔍 DEBUG: Cache updated, size={len(self._cache[session_id])}")

        # Persist to database
        metadata_json = json.dumps(metadata or {})

        with sqlite3.connect(self.db_path) as conn:
            # Insert user message
            conn.execute(
                """
                INSERT INTO conversations (session_id, timestamp, role, content, metadata)
                VALUES (?, ?, 'user', ?, ?)
                """,
                (session_id, timestamp, user_message, metadata_json),
            )

            # Insert assistant message
            conn.execute(
                """
                INSERT INTO conversations (session_id, timestamp, role, content, metadata)
                VALUES (?, ?, 'assistant', ?, ?)
                """,
                (session_id, timestamp + 0.001, assistant_message, metadata_json),
            )

            conn.commit()
            logger.info(f"✅ DEBUG: Saved turn to database {self.db_path}")

        # Cleanup old messages if needed
        self._cleanup_old_messages(session_id)
        logger.info(f"✅ DEBUG: add_turn() completed for session {session_id}")

    def get_context_messages(self, session_id: str, limit: int | None = None) -> list[Message]:
        """Get context messages for session.

        Parameters
        ----------
        session_id
            Session identifier
        limit
            Maximum number of exchanges to return (default: all up to max_exchanges)

        Returns
        -------
        list[Message]
            Context messages in chronological order
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"🔍 DEBUG: get_context_messages() - session_id={session_id}, limit={limit}")

        if limit is None:
            limit = self.max_exchanges

        # Try cache first
        if session_id in self._cache and limit <= self.cache_size:
            logger.info(f"🔍 DEBUG: Using cache for {session_id}, cache_size={len(self._cache[session_id])}")
            turns = list(self._cache[session_id])[-limit:]
            messages = []
            for turn in turns:
                messages.append(Message(role="user", content=turn.user_message))
                messages.append(Message(role="assistant", content=turn.assistant_message))
            logger.info(f"✅ DEBUG: Returning {len(messages)} messages from cache")
            return messages

        # Load from database
        logger.info(f"🔍 DEBUG: Cache miss or large limit, loading from database {self.db_path}")
        messages = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT role, content FROM conversations
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit * 2),  # *2 because each turn = 2 messages
            )

            rows = cursor.fetchall()
            logger.info(f"🔍 DEBUG: Database returned {len(rows)} rows")

            # Reverse to get chronological order
            for role, content in reversed(rows):
                messages.append(Message(role=role, content=content))

        logger.info(f"✅ DEBUG: Returning {len(messages)} messages from database")
        return messages

    def get_turns(self, session_id: str, limit: int | None = None) -> list[ConversationTurn]:
        """Get conversation turns for session.

        Parameters
        ----------
        session_id
            Session identifier
        limit
            Maximum number of turns to return

        Returns
        -------
        list[ConversationTurn]
            Conversation turns in chronological order
        """
        if limit is None:
            limit = self.max_exchanges

        turns = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT timestamp, content, metadata, role
                FROM conversations
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            )

            rows = cursor.fetchall()

            # Group by timestamp (user + assistant messages)
            current_turn: dict[str, Any] = {}
            for timestamp, content, metadata_json, role in rows:
                if role == "user":
                    current_turn = {
                        "timestamp": timestamp,
                        "user_message": content,
                        "metadata": json.loads(metadata_json) if metadata_json else {},
                    }
                elif role == "assistant" and current_turn:
                    current_turn["assistant_message"] = content
                    turns.append(ConversationTurn.from_dict(current_turn))
                    current_turn = {}

        return turns[-limit:] if limit else turns

    def clear_session(self, session_id: str) -> None:
        """Clear session memory.

        Parameters
        ----------
        session_id
            Session identifier
        """
        # Clear cache
        if session_id in self._cache:
            del self._cache[session_id]

        # Clear database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM conversations WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()

    def has_context(self, session_id: str) -> bool:
        """Check if session has context.

        Parameters
        ----------
        session_id
            Session identifier

        Returns
        -------
        bool
            True if session has context
        """
        # Check cache first
        if session_id in self._cache and len(self._cache[session_id]) > 0:
            return True

        # Check database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            count = row[0] if row else 0
            return bool(count > 0)

    def get_session_count(self) -> int:
        """Get total number of active sessions.

        Returns
        -------
        int
            Number of sessions with messages
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM conversations"
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def _cleanup_old_messages(self, session_id: str) -> None:
        """Remove old messages beyond max_exchanges limit.

        Parameters
        ----------
        session_id
            Session identifier
        """
        with sqlite3.connect(self.db_path) as conn:
            # Count current messages (pairs of user+assistant)
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM conversations
                WHERE session_id = ? AND role = 'user'
                """,
                (session_id,),
            )
            count = cursor.fetchone()[0]

            if count > self.max_exchanges:
                # Delete oldest messages
                to_delete = count - self.max_exchanges

                # Get timestamps of oldest exchanges
                cursor = conn.execute(
                    """
                    SELECT timestamp FROM conversations
                    WHERE session_id = ? AND role = 'user'
                    ORDER BY timestamp ASC
                    LIMIT ?
                    """,
                    (session_id, to_delete),
                )

                old_timestamps = [row[0] for row in cursor.fetchall()]

                if old_timestamps:
                    # Delete all messages with these timestamps (user + assistant)
                    placeholders = ",".join("?" * len(old_timestamps))
                    conn.execute(
                        f"""
                        DELETE FROM conversations
                        WHERE session_id = ? AND timestamp IN ({placeholders})
                        """,
                        (session_id, *old_timestamps),
                    )

                    # Also delete assistant messages right after
                    for ts in old_timestamps:
                        conn.execute(
                            """
                            DELETE FROM conversations
                            WHERE session_id = ? AND role = 'assistant'
                            AND timestamp BETWEEN ? AND ?
                            """,
                            (session_id, ts, ts + 1.0),
                        )

                    conn.commit()

    def get_all_sessions(self) -> list[str]:
        """Get list of all session IDs.

        Returns
        -------
        list[str]
            List of session identifiers
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT session_id FROM conversations ORDER BY session_id"
            )
            return [row[0] for row in cursor.fetchall()]

    def export_session(self, session_id: str) -> dict[str, Any]:
        """Export session data for backup/debugging.

        Parameters
        ----------
        session_id
            Session identifier

        Returns
        -------
        dict
            Session data with all turns
        """
        turns = self.get_turns(session_id)
        return {
            "session_id": session_id,
            "turn_count": len(turns),
            "turns": [turn.to_dict() for turn in turns],
        }

    def save_session_state(
        self,
        session_id: str,
        pending_confirmation: bool,
        pending_plan: list[dict[str, Any]] | None = None,
        confirmation_question: str = "",
    ) -> None:
        """Save session confirmation state.

        Parameters
        ----------
        session_id
            Session identifier
        pending_confirmation
            Whether confirmation is pending
        pending_plan
            Plan waiting for confirmation
        confirmation_question
            Question to ask user
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(
            f"🔍 DEBUG: save_session_state() - session={session_id}, "
            f"pending={pending_confirmation}, plan_len={len(pending_plan) if pending_plan else 0}"
        )

        pending_plan_json = json.dumps(pending_plan or [])

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO session_state
                (session_id, pending_confirmation, pending_plan, confirmation_question, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    session_id,
                    1 if pending_confirmation else 0,
                    pending_plan_json,
                    confirmation_question,
                ),
            )
            conn.commit()

        logger.info(f"✅ DEBUG: Saved session state for {session_id}")

    def get_session_state(self, session_id: str) -> dict[str, Any]:
        """Get session confirmation state.

        Parameters
        ----------
        session_id
            Session identifier

        Returns
        -------
        dict
            Session state with pending_confirmation, pending_plan, confirmation_question
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"🔍 DEBUG: get_session_state() - session={session_id}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT pending_confirmation, pending_plan, confirmation_question
                FROM session_state
                WHERE session_id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()

            if row:
                pending_confirmation, pending_plan_json, confirmation_question = row
                pending_plan = json.loads(pending_plan_json) if pending_plan_json else []

                logger.info(
                    f"✅ DEBUG: Found session state - pending={bool(pending_confirmation)}, "
                    f"plan_len={len(pending_plan)}"
                )

                return {
                    "pending_confirmation": bool(pending_confirmation),
                    "pending_plan": pending_plan,
                    "confirmation_question": confirmation_question or "",
                }

        logger.info(f"✅ DEBUG: No session state found for {session_id}, using defaults")
        return {
            "pending_confirmation": False,
            "pending_plan": [],
            "confirmation_question": "",
        }

    def clear_session_state(self, session_id: str) -> None:
        """Clear session confirmation state.

        Parameters
        ----------
        session_id
            Session identifier
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"🔍 DEBUG: clear_session_state() - session={session_id}")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM session_state WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()

        logger.info(f"✅ DEBUG: Cleared session state for {session_id}")

