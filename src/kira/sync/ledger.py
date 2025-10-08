"""Sync ledger for tracking remote state and preventing echo loops (Phase 4, Point 15).

The sync ledger maintains a record of what we've seen from each remote entity:
- remote_id → version_seen, etag_seen, last_sync_ts

This enables:
1. Echo loop prevention: Ignore updates that mirror what we just wrote
2. Conflict detection: Compare timestamps to resolve conflicts
3. Change detection: Only sync when remote actually changed
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..core.time import format_utc_iso8601, get_current_utc, parse_utc_iso8601

__all__ = [
    "SyncLedger",
    "SyncLedgerEntry",
    "create_sync_ledger",
    "resolve_conflict",
    "should_import_remote_update",
]


@dataclass
class SyncLedgerEntry:
    """Entry in sync ledger tracking remote entity state.

    Attributes
    ----------
    remote_id : str
        ID in remote system
    version_seen : int
        Last version we observed
    etag_seen : str | None
        Last ETag we observed
    last_sync_ts : str
        Timestamp of last sync (ISO-8601 UTC)
    entity_id : str | None
        Local entity ID (if mapped)
    """

    remote_id: str
    version_seen: int
    etag_seen: str | None
    last_sync_ts: str
    entity_id: str | None = None


class SyncLedger:
    """Sync ledger for tracking remote state (Phase 4, Point 15).

    Maintains ledger: remote_id → (version_seen, etag, last_sync_ts)

    Purpose:
    - Prevent echo loops by ignoring mirrored updates
    - Detect conflicts by comparing versions/timestamps
    - Track what we've seen from each remote
    """

    def __init__(self, db_path: Path | str) -> None:
        """Initialize sync ledger.

        Parameters
        ----------
        db_path
            Path to SQLite database
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_ledger (
                remote_id TEXT PRIMARY KEY,
                version_seen INTEGER NOT NULL,
                etag_seen TEXT,
                last_sync_ts TEXT NOT NULL,
                entity_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for entity_id lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sync_ledger_entity_id
            ON sync_ledger(entity_id)
        """
        )

        conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def get_entry(self, remote_id: str) -> SyncLedgerEntry | None:
        """Get ledger entry for remote entity.

        Parameters
        ----------
        remote_id
            Remote entity ID

        Returns
        -------
        SyncLedgerEntry | None
            Entry if exists, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM sync_ledger WHERE remote_id = ?", (remote_id,))

        row = cursor.fetchone()
        if row is None:
            return None

        return SyncLedgerEntry(
            remote_id=row["remote_id"],
            version_seen=row["version_seen"],
            etag_seen=row["etag_seen"],
            last_sync_ts=row["last_sync_ts"],
            entity_id=row["entity_id"],
        )

    def record_sync(
        self,
        remote_id: str,
        version: int,
        *,
        etag: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        """Record that we've synced a remote entity.

        Parameters
        ----------
        remote_id
            Remote entity ID
        version
            Version we observed
        etag
            Optional ETag we observed
        entity_id
            Optional local entity ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())

        cursor.execute(
            """
            INSERT OR REPLACE INTO sync_ledger
            (remote_id, version_seen, etag_seen, last_sync_ts, entity_id)
            VALUES (?, ?, ?, ?, ?)
        """,
            (remote_id, version, etag, now, entity_id),
        )

        conn.commit()

    def is_echo(self, remote_id: str, remote_version: int) -> bool:
        """Check if remote update is an echo of our write (Phase 4, Point 15).

        Echo detection: If remote version matches what we last wrote,
        it's likely an echo and should be ignored.

        Parameters
        ----------
        remote_id
            Remote entity ID
        remote_version
            Version from remote

        Returns
        -------
        bool
            True if this appears to be an echo
        """
        entry = self.get_entry(remote_id)

        if entry is None:
            # Never seen before, not an echo
            return False

        # If remote version matches what we last saw/wrote, it's an echo
        return remote_version == entry.version_seen

    def should_import(
        self,
        remote_id: str,
        remote_version: int,
        remote_etag: str | None = None,
    ) -> bool:
        """Check if we should import a remote update.

        Criteria:
        - Not an echo (version changed)
        - ETag changed (if provided)

        Parameters
        ----------
        remote_id
            Remote entity ID
        remote_version
            Remote version
        remote_etag
            Optional remote ETag

        Returns
        -------
        bool
            True if we should import
        """
        entry = self.get_entry(remote_id)

        if entry is None:
            # Never seen before, should import
            return True

        # Check version
        if remote_version != entry.version_seen:
            return True

        # Check ETag if available
        if remote_etag and remote_etag != entry.etag_seen:
            return True

        # No changes detected
        return False

    def get_entity_id(self, remote_id: str) -> str | None:
        """Get local entity ID for remote entity.

        Parameters
        ----------
        remote_id
            Remote entity ID

        Returns
        -------
        str | None
            Local entity ID if mapped
        """
        entry = self.get_entry(remote_id)
        return entry.entity_id if entry else None

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SyncLedger:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


def create_sync_ledger(vault_path: Path) -> SyncLedger:
    """Create sync ledger for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    SyncLedger
        Configured sync ledger
    """
    db_path = vault_path / "artifacts" / "sync_ledger.db"
    return SyncLedger(db_path)


def should_import_remote_update(
    ledger: SyncLedger,
    remote_id: str,
    remote_version: int,
    remote_etag: str | None = None,
) -> bool:
    """Determine if remote update should be imported (Phase 4, Point 15).

    Prevents echo loops by checking ledger.

    Parameters
    ----------
    ledger
        Sync ledger
    remote_id
        Remote entity ID
    remote_version
        Remote version
    remote_etag
        Optional remote ETag

    Returns
    -------
    bool
        True if should import
    """
    # Check for echo
    if ledger.is_echo(remote_id, remote_version):
        return False

    # Check if changed
    return ledger.should_import(remote_id, remote_version, remote_etag)


def resolve_conflict(
    local_last_write_ts: str,
    remote_last_write_ts: str,
) -> Literal["local", "remote", "tie"]:
    """Resolve sync conflict using latest-wins policy (Phase 4, Point 15).

    Policy: Latest-wins by last_write_ts

    Parameters
    ----------
    local_last_write_ts
        Local last write timestamp (ISO-8601 UTC)
    remote_last_write_ts
        Remote last write timestamp (ISO-8601 UTC)

    Returns
    -------
    Literal["local", "remote", "tie"]
        Winner of conflict resolution
    """
    try:
        local_dt = parse_utc_iso8601(local_last_write_ts)
        remote_dt = parse_utc_iso8601(remote_last_write_ts)

        if local_dt > remote_dt:
            return "local"
        if remote_dt > local_dt:
            return "remote"
        return "tie"
    except (ValueError, AttributeError):
        # If timestamps can't be parsed, treat as tie
        return "tie"
