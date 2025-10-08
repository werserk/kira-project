"""Event idempotency and deduplication (Phase 2, Point 7).

Ensures re-publishing the same logical event is a no-op.
Tracks seen events in SQLite with TTL cleanup.

event_id = sha256(source, external_id, normalized_payload)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .time import format_utc_iso8601, get_current_utc, parse_utc_iso8601

__all__ = [
    "EventDedupeStore",
    "generate_event_id",
    "normalize_payload_for_hashing",
    "create_dedupe_store",
]


def normalize_payload_for_hashing(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.
    
    Ensures identical logical payloads produce identical hashes.
    
    Parameters
    ----------
    payload
        Event payload to normalize
        
    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()
    
    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)
    
    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def generate_event_id(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).
    
    event_id = sha256(source, external_id, normalized_payload)
    
    Identical logical events produce identical IDs,
    enabling deduplication.
    
    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload
        
    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)
        
    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)
    
    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)
    
    # Hash
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    event_id = hash_obj.hexdigest()
    
    return event_id


class EventDedupeStore:
    """Dedupe store for tracking seen events (Phase 2, Point 7).
    
    Tracks seen_events(event_id, first_seen_ts) in SQLite.
    Provides TTL-based cleanup.
    
    Re-publishing the same logical event is a no-op.
    """
    
    def __init__(self, db_path: Path | str) -> None:
        """Initialize dedupe store.
        
        Parameters
        ----------
        db_path
            Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create seen_events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """)
        
        # Index for TTL cleanup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """)
        
        conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def is_duplicate(self, event_id: str) -> bool:
        """Check if event has been seen before.
        
        Parameters
        ----------
        event_id
            Event ID to check
            
        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT event_id FROM seen_events WHERE event_id = ?",
            (event_id,)
        )
        
        return cursor.fetchone() is not None
    
    def mark_seen(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.
        
        If event was already seen, updates last_seen_ts and seen_count.
        
        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata
            
        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Check if already exists
        cursor.execute(
            "SELECT seen_count FROM seen_events WHERE event_id = ?",
            (event_id,)
        )
        row = cursor.fetchone()
        
        if row is not None:
            # Update existing
            cursor.execute("""
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """, (now, event_id))
            conn.commit()
            return False  # Duplicate
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """, (event_id, now, now, source, external_id, metadata_json))
            conn.commit()
            return True  # First time
    
    def get_event_info(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.
        
        Parameters
        ----------
        event_id
            Event ID
            
        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM seen_events WHERE event_id = ?",
            (event_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }
    
    def cleanup_old_events(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).
        
        Parameters
        ----------
        ttl_days
            Time-to-live in days
            
        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)
        
        # Delete old events
        cursor.execute(
            "DELETE FROM seen_events WHERE first_seen_ts < ?",
            (cutoff_str,)
        )
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        return deleted_count
    
    def get_stats(self) -> dict[str, Any]:
        """Get dedupe store statistics.
        
        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]
        
        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]
        
        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0
        
        # By source
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """)
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self) -> EventDedupeStore:
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


def create_dedupe_store(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.
    
    Parameters
    ----------
    vault_path
        Path to vault
        
    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path / "artifacts" / "dedupe.db"
    return EventDedupeStore(db_path)

