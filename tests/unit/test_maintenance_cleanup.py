"""Tests for TTL cleanup (Phase 10, Point 27).

DoD: Storage usage stays bounded.
"""

import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kira.maintenance.cleanup import (
    CleanupConfig,
    CleanupStats,
    cleanup_dedupe_store,
    cleanup_logs,
    cleanup_quarantine,
    run_cleanup_all,
)


@pytest.fixture
def test_env():
    """Create test environment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        artifacts_dir = vault_path / "artifacts"
        artifacts_dir.mkdir()

        yield vault_path, artifacts_dir


def test_cleanup_dedupe_store_empty():
    """Test cleanup of non-existent dedupe store."""
    removed = cleanup_dedupe_store(Path("/nonexistent/dedupe.db"), ttl_days=30)
    assert removed == 0


def test_cleanup_dedupe_store_removes_old(test_env):
    """Test DoD: Old dedupe records removed."""
    vault_path, artifacts_dir = test_env

    db_path = artifacts_dir / "dedupe.db"

    # Create dedupe database
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE seen_events (
            event_id TEXT PRIMARY KEY,
            first_seen_ts TEXT NOT NULL,
            last_seen_ts TEXT NOT NULL
        )
    """
    )

    # Insert old and new records
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=60)).isoformat()
    recent_ts = (now - timedelta(days=1)).isoformat()

    conn.execute("INSERT INTO seen_events VALUES (?, ?, ?)", ("old-event", old_ts, old_ts))
    conn.execute("INSERT INTO seen_events VALUES (?, ?, ?)", ("recent-event", recent_ts, recent_ts))
    conn.commit()
    conn.close()

    # Cleanup with 30-day TTL
    removed = cleanup_dedupe_store(db_path, ttl_days=30)

    # Should remove old event
    assert removed == 1

    # Verify only recent event remains
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT event_id FROM seen_events")
    remaining = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert "recent-event" in remaining
    assert "old-event" not in remaining


def test_cleanup_quarantine_empty(test_env):
    """Test cleanup of empty quarantine."""
    vault_path, artifacts_dir = test_env

    quarantine_dir = artifacts_dir / "quarantine"

    files_removed, bytes_freed = cleanup_quarantine(quarantine_dir, ttl_days=90)

    assert files_removed == 0
    assert bytes_freed == 0


def test_cleanup_quarantine_removes_old(test_env):
    """Test DoD: Old quarantine files removed."""
    vault_path, artifacts_dir = test_env

    quarantine_dir = artifacts_dir / "quarantine"
    quarantine_dir.mkdir()

    # Create old file
    old_file = quarantine_dir / "old-quarantine.json"
    old_file.write_text('{"error": "old"}')

    # Set old modification time (100 days ago)
    old_time = time.time() - (100 * 24 * 3600)
    import os

    os.utime(old_file, (old_time, old_time))

    # Create recent file
    recent_file = quarantine_dir / "recent-quarantine.json"
    recent_file.write_text('{"error": "recent"}')

    # Cleanup with 90-day TTL
    files_removed, bytes_freed = cleanup_quarantine(quarantine_dir, ttl_days=90)

    # Should remove old file
    assert files_removed == 1
    assert bytes_freed > 0

    # Verify files
    assert not old_file.exists()
    assert recent_file.exists()


def test_cleanup_logs_empty(test_env):
    """Test cleanup of empty log directory."""
    vault_path, artifacts_dir = test_env

    log_dir = artifacts_dir / "logs"

    files_removed, bytes_freed = cleanup_logs(log_dir, ttl_days=7)

    assert files_removed == 0
    assert bytes_freed == 0


def test_cleanup_logs_removes_old(test_env):
    """Test DoD: Old log files removed."""
    vault_path, artifacts_dir = test_env

    log_dir = artifacts_dir / "logs"
    log_dir.mkdir()

    # Create old log
    old_log = log_dir / "old.log"
    old_log.write_text("old log content")

    # Set old modification time (10 days ago)
    old_time = time.time() - (10 * 24 * 3600)
    import os

    os.utime(old_log, (old_time, old_time))

    # Create recent log
    recent_log = log_dir / "recent.log"
    recent_log.write_text("recent log content")

    # Cleanup with 7-day TTL
    files_removed, bytes_freed = cleanup_logs(log_dir, ttl_days=7)

    # Should remove old log
    assert files_removed == 1
    assert bytes_freed > 0

    # Verify files
    assert not old_log.exists()
    assert recent_log.exists()


def test_run_cleanup_all(test_env):
    """Test DoD: Run all cleanup tasks."""
    vault_path, artifacts_dir = test_env

    # Setup: Create some old data

    # 1. Dedupe database
    db_path = artifacts_dir / "dedupe.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE seen_events (
            event_id TEXT PRIMARY KEY,
            first_seen_ts TEXT NOT NULL,
            last_seen_ts TEXT NOT NULL
        )
    """
    )
    old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    conn.execute("INSERT INTO seen_events VALUES (?, ?, ?)", ("old", old_ts, old_ts))
    conn.commit()
    conn.close()

    # 2. Quarantine
    quarantine_dir = artifacts_dir / "quarantine"
    quarantine_dir.mkdir()
    old_q_file = quarantine_dir / "old.json"
    old_q_file.write_text("{}")
    old_time = time.time() - (100 * 24 * 3600)
    import os

    os.utime(old_q_file, (old_time, old_time))

    # 3. Logs
    log_dir = artifacts_dir / "logs"
    log_dir.mkdir()
    old_log = log_dir / "old.log"
    old_log.write_text("old")
    os.utime(old_log, (old_time, old_time))

    # Run cleanup
    config = CleanupConfig(
        dedupe_ttl_days=30,
        quarantine_ttl_days=90,
        log_ttl_days=7,
    )

    stats = run_cleanup_all(vault_path, config)

    # Verify cleanup happened
    assert isinstance(stats, CleanupStats)
    assert stats.dedupe_removed >= 1
    assert stats.quarantine_removed >= 1
    assert stats.logs_removed >= 1
    assert stats.bytes_freed > 0


def test_cleanup_config_defaults():
    """Test cleanup config defaults."""
    config = CleanupConfig()

    assert config.dedupe_ttl_days == 30
    assert config.quarantine_ttl_days == 90
    assert config.log_ttl_days == 7


def test_cleanup_stats():
    """Test cleanup stats dataclass."""
    stats = CleanupStats(
        dedupe_removed=10,
        quarantine_removed=5,
        logs_removed=3,
        bytes_freed=1024,
    )

    assert stats.dedupe_removed == 10
    assert stats.quarantine_removed == 5
    assert stats.logs_removed == 3
    assert stats.bytes_freed == 1024


def test_dod_storage_stays_bounded(test_env):
    """Test DoD: Storage usage stays bounded.

    Critical test: Cleanup prevents unbounded growth.
    """
    vault_path, artifacts_dir = test_env

    # Create dedupe database with many old records
    db_path = artifacts_dir / "dedupe.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE seen_events (
            event_id TEXT PRIMARY KEY,
            first_seen_ts TEXT NOT NULL,
            last_seen_ts TEXT NOT NULL
        )
    """
    )

    # Insert 1000 old records
    old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    for i in range(1000):
        conn.execute("INSERT INTO seen_events VALUES (?, ?, ?)", (f"event-{i}", old_ts, old_ts))
    conn.commit()
    conn.close()

    # Get initial size
    initial_size = db_path.stat().st_size

    # Run cleanup
    removed = cleanup_dedupe_store(db_path, ttl_days=30)

    # Should remove all 1000 records
    assert removed == 1000

    # Size should be reduced (after VACUUM)
    final_size = db_path.stat().st_size
    assert final_size < initial_size
