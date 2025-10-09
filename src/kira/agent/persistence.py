"""Persistence layer for agent state.

Phase 2, Item 10: Persistence layer for long runs.
Enables state recovery after process restart.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .state import AgentState

logger = logging.getLogger(__name__)

__all__ = ["StatePersistence", "FileStatePersistence", "SQLiteStatePersistence", "create_persistence"]


class StatePersistence:
    """Base class for state persistence."""

    def save_state(self, trace_id: str, state: AgentState) -> None:
        """Save agent state.

        Parameters
        ----------
        trace_id
            Trace/session identifier
        state
            Agent state to save
        """
        raise NotImplementedError

    def load_state(self, trace_id: str) -> dict[str, Any] | None:
        """Load agent state.

        Parameters
        ----------
        trace_id
            Trace/session identifier

        Returns
        -------
        dict | None
            State data or None if not found
        """
        raise NotImplementedError

    def delete_state(self, trace_id: str) -> None:
        """Delete agent state.

        Parameters
        ----------
        trace_id
            Trace/session identifier
        """
        raise NotImplementedError

    def list_states(self) -> list[str]:
        """List all saved trace IDs.

        Returns
        -------
        list[str]
            List of trace IDs
        """
        raise NotImplementedError


class FileStatePersistence(StatePersistence):
    """File-based state persistence.

    Stores each state as a JSON file: {trace_id}.json
    """

    def __init__(self, storage_path: Path) -> None:
        """Initialize file persistence.

        Parameters
        ----------
        storage_path
            Directory to store state files
        """
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, trace_id: str) -> Path:
        """Get file path for trace ID.

        Parameters
        ----------
        trace_id
            Trace identifier

        Returns
        -------
        Path
            File path
        """
        # Sanitize trace_id for filesystem
        safe_id = trace_id.replace("/", "_").replace("\\", "_")
        return self.storage_path / f"{safe_id}.json"

    def save_state(self, trace_id: str, state: AgentState) -> None:
        """Save agent state to file."""
        file_path = self._get_file_path(trace_id)

        try:
            state_data = state.to_dict()
            with file_path.open("w") as f:
                json.dump(state_data, f, indent=2)

            logger.info(f"Saved state for trace {trace_id} to {file_path}")

        except Exception as e:
            logger.error(f"Failed to save state for {trace_id}: {e}", exc_info=True)
            raise

    def load_state(self, trace_id: str) -> dict[str, Any] | None:
        """Load agent state from file."""
        file_path = self._get_file_path(trace_id)

        if not file_path.exists():
            logger.debug(f"No saved state found for trace {trace_id}")
            return None

        try:
            with file_path.open() as f:
                state_data = json.load(f)

            logger.info(f"Loaded state for trace {trace_id} from {file_path}")
            return state_data

        except Exception as e:
            logger.error(f"Failed to load state for {trace_id}: {e}", exc_info=True)
            return None

    def delete_state(self, trace_id: str) -> None:
        """Delete agent state file."""
        file_path = self._get_file_path(trace_id)

        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted state for trace {trace_id}")
            except Exception as e:
                logger.error(f"Failed to delete state for {trace_id}: {e}", exc_info=True)

    def list_states(self) -> list[str]:
        """List all saved trace IDs."""
        states = []
        for file_path in self.storage_path.glob("*.json"):
            # Extract trace_id from filename
            trace_id = file_path.stem
            states.append(trace_id)

        return states


class SQLiteStatePersistence(StatePersistence):
    """SQLite-based state persistence.

    Stores states in SQLite database with indexing and querying support.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize SQLite persistence.

        Parameters
        ----------
        db_path
            Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_states (
                    trace_id TEXT PRIMARY KEY,
                    state_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_updated_at
                ON agent_states(updated_at)
                """
            )
            conn.commit()

    def save_state(self, trace_id: str, state: AgentState) -> None:
        """Save agent state to database."""
        try:
            state_data = state.to_dict()
            state_json = json.dumps(state_data)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO agent_states (trace_id, state_data, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (trace_id, state_json),
                )
                conn.commit()

            logger.info(f"Saved state for trace {trace_id} to database")

        except Exception as e:
            logger.error(f"Failed to save state for {trace_id}: {e}", exc_info=True)
            raise

    def load_state(self, trace_id: str) -> dict[str, Any] | None:
        """Load agent state from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT state_data FROM agent_states
                    WHERE trace_id = ?
                    """,
                    (trace_id,),
                )
                row = cursor.fetchone()

                if row:
                    state_data = json.loads(row[0])
                    logger.info(f"Loaded state for trace {trace_id} from database")
                    return state_data
                else:
                    logger.debug(f"No saved state found for trace {trace_id}")
                    return None

        except Exception as e:
            logger.error(f"Failed to load state for {trace_id}: {e}", exc_info=True)
            return None

    def delete_state(self, trace_id: str) -> None:
        """Delete agent state from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    DELETE FROM agent_states
                    WHERE trace_id = ?
                    """,
                    (trace_id,),
                )
                conn.commit()

            logger.info(f"Deleted state for trace {trace_id}")

        except Exception as e:
            logger.error(f"Failed to delete state for {trace_id}: {e}", exc_info=True)

    def list_states(self) -> list[str]:
        """List all saved trace IDs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT trace_id FROM agent_states
                    ORDER BY updated_at DESC
                    """
                )
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to list states: {e}", exc_info=True)
            return []


def create_persistence(
    storage_type: str = "file",
    storage_path: Path | None = None,
) -> StatePersistence:
    """Factory function to create state persistence.

    Parameters
    ----------
    storage_type
        Type of persistence: "file" or "sqlite"
    storage_path
        Path to storage location

    Returns
    -------
    StatePersistence
        Configured persistence layer
    """
    if storage_path is None:
        storage_path = Path.cwd() / "artifacts" / "agent_states"

    if storage_type == "sqlite":
        db_path = storage_path / "agent_states.db"
        return SQLiteStatePersistence(db_path)
    else:
        # Default to file-based
        return FileStatePersistence(storage_path)

