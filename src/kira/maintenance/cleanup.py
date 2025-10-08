"""TTL-based cleanup for Kira (Phase 10, Point 27).

Scheduled jobs to purge old data:
- Seen events (dedupe store)
- Logs
- Quarantine files
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "CleanupConfig",
    "CleanupStats",
    "cleanup_dedupe_store",
    "cleanup_quarantine",
    "cleanup_logs",
    "run_cleanup_all",
]


@dataclass
class CleanupConfig:
    """Configuration for cleanup tasks.

    Attributes
    ----------
    dedupe_ttl_days : int
        Days to keep dedupe records (default: 30)
    quarantine_ttl_days : int
        Days to keep quarantine files (default: 90)
    log_ttl_days : int
        Days to keep log files (default: 7)
    """

    dedupe_ttl_days: int = 30
    quarantine_ttl_days: int = 90
    log_ttl_days: int = 7


@dataclass
class CleanupStats:
    """Statistics from cleanup run.

    Attributes
    ----------
    dedupe_removed : int
        Number of dedupe records removed
    quarantine_removed : int
        Number of quarantine files removed
    logs_removed : int
        Number of log files removed
    bytes_freed : int
        Bytes of storage freed
    """

    dedupe_removed: int = 0
    quarantine_removed: int = 0
    logs_removed: int = 0
    bytes_freed: int = 0


def cleanup_dedupe_store(
    db_path: Path,
    ttl_days: int = 30,
) -> int:
    """Clean old entries from dedupe store (Phase 10, Point 27).

    DoD: Storage usage stays bounded.

    Parameters
    ----------
    db_path
        Path to dedupe SQLite database
    ttl_days
        Days to keep records

    Returns
    -------
    int
        Number of records removed
    """
    if not db_path.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    cutoff_str = cutoff.isoformat()

    conn = sqlite3.connect(db_path)
    try:
        # Delete old records
        cursor = conn.execute(
            """
            DELETE FROM seen_events
            WHERE first_seen_ts < ?
        """,
            (cutoff_str,),
        )

        removed = cursor.rowcount
        conn.commit()

        # Vacuum to reclaim space
        conn.execute("VACUUM")

        return removed
    finally:
        conn.close()


def cleanup_quarantine(
    quarantine_dir: Path,
    ttl_days: int = 90,
) -> tuple[int, int]:
    """Clean old quarantine files (Phase 10, Point 27).

    DoD: Storage usage stays bounded.

    Parameters
    ----------
    quarantine_dir
        Path to quarantine directory
    ttl_days
        Days to keep files

    Returns
    -------
    tuple[int, int]
        (files_removed, bytes_freed)
    """
    if not quarantine_dir.exists():
        return 0, 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)

    files_removed = 0
    bytes_freed = 0

    for file_path in quarantine_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # Check file modification time
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

        if mtime < cutoff:
            # Get size before deletion
            size = file_path.stat().st_size

            # Delete file
            file_path.unlink()

            files_removed += 1
            bytes_freed += size

    return files_removed, bytes_freed


def cleanup_logs(
    log_dir: Path,
    ttl_days: int = 7,
) -> tuple[int, int]:
    """Clean old log files (Phase 10, Point 27).

    DoD: Storage usage stays bounded.

    Parameters
    ----------
    log_dir
        Path to log directory
    ttl_days
        Days to keep files

    Returns
    -------
    tuple[int, int]
        (files_removed, bytes_freed)
    """
    if not log_dir.exists():
        return 0, 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)

    files_removed = 0
    bytes_freed = 0

    for file_path in log_dir.rglob("*.log*"):
        if not file_path.is_file():
            continue

        # Check file modification time
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

        if mtime < cutoff:
            # Get size before deletion
            size = file_path.stat().st_size

            # Delete file
            file_path.unlink()

            files_removed += 1
            bytes_freed += size

    return files_removed, bytes_freed


def run_cleanup_all(
    vault_path: Path,
    config: CleanupConfig | None = None,
) -> CleanupStats:
    """Run all cleanup tasks (Phase 10, Point 27).

    DoD: Storage usage stays bounded.

    Parameters
    ----------
    vault_path
        Path to vault root
    config
        Cleanup configuration

    Returns
    -------
    CleanupStats
        Statistics from cleanup
    """
    if config is None:
        config = CleanupConfig()

    stats = CleanupStats()

    # 1. Cleanup dedupe store
    dedupe_path = vault_path / "artifacts" / "dedupe.db"
    stats.dedupe_removed = cleanup_dedupe_store(dedupe_path, config.dedupe_ttl_days)

    # 2. Cleanup quarantine
    quarantine_path = vault_path / "artifacts" / "quarantine"
    files, bytes_freed = cleanup_quarantine(quarantine_path, config.quarantine_ttl_days)
    stats.quarantine_removed = files
    stats.bytes_freed += bytes_freed

    # 3. Cleanup logs
    log_path = vault_path / "artifacts" / "logs"
    files, bytes_freed = cleanup_logs(log_path, config.log_ttl_days)
    stats.logs_removed = files
    stats.bytes_freed += bytes_freed

    return stats
