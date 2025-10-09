"""Tests for sync ledger and echo loop prevention (Phase 4, Point 15)."""

import tempfile
from pathlib import Path

from kira.sync.contract import create_kira_sync_contract, create_remote_sync_contract
from kira.sync.ledger import (
    SyncLedger,
    create_sync_ledger,
    resolve_conflict,
    should_import_remote_update,
)


def test_sync_ledger_initialization():
    """Test sync ledger initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        ledger = SyncLedger(db_path)

        assert ledger.db_path == db_path
        assert db_path.exists()

        ledger.close()


def test_sync_ledger_record_sync():
    """Test recording a sync."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            ledger.record_sync(
                remote_id="gcal-event-123",
                version=5,
                etag="etag-abc",
                entity_id="event-local-456",
            )

            # Retrieve entry
            entry = ledger.get_entry("gcal-event-123")

            assert entry is not None
            assert entry.remote_id == "gcal-event-123"
            assert entry.version_seen == 5
            assert entry.etag_seen == "etag-abc"
            assert entry.entity_id == "event-local-456"


def test_sync_ledger_get_entry_not_found():
    """Test getting entry that doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            entry = ledger.get_entry("nonexistent")
            assert entry is None


def test_sync_ledger_is_echo_true():
    """Test DoD: Echo detection when version matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # Record that we synced version 3
            ledger.record_sync("gcal-event-1", version=3)

            # Remote reports version 3 - this is an echo
            assert ledger.is_echo("gcal-event-1", remote_version=3) is True


def test_sync_ledger_is_echo_false():
    """Test echo detection when version changed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # Record that we synced version 3
            ledger.record_sync("gcal-event-1", version=3)

            # Remote reports version 4 - not an echo
            assert ledger.is_echo("gcal-event-1", remote_version=4) is False


def test_sync_ledger_is_echo_never_seen():
    """Test echo detection for entity never seen before."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # Never seen before - not an echo
            assert ledger.is_echo("new-entity", remote_version=1) is False


def test_sync_ledger_should_import_new():
    """Test should import for new entity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # Never seen before - should import
            assert ledger.should_import("new-entity", remote_version=1) is True


def test_sync_ledger_should_import_version_changed():
    """Test should import when version changed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            ledger.record_sync("gcal-event-1", version=3)

            # Version changed - should import
            assert ledger.should_import("gcal-event-1", remote_version=4) is True


def test_sync_ledger_should_import_no_change():
    """Test should not import when nothing changed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            ledger.record_sync("gcal-event-1", version=3, etag="etag-abc")

            # Nothing changed - should not import
            assert ledger.should_import("gcal-event-1", remote_version=3, remote_etag="etag-abc") is False


def test_sync_ledger_should_import_etag_changed():
    """Test should import when ETag changed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            ledger.record_sync("gcal-event-1", version=3, etag="etag-old")

            # ETag changed - should import
            assert ledger.should_import("gcal-event-1", remote_version=3, remote_etag="etag-new") is True


def test_sync_ledger_get_entity_id():
    """Test getting local entity ID for remote."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            ledger.record_sync("gcal-123", version=1, entity_id="event-local-456")

            entity_id = ledger.get_entity_id("gcal-123")
            assert entity_id == "event-local-456"


def test_should_import_remote_update_echo():
    """Test helper function rejects echoes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            ledger.record_sync("gcal-1", version=5)

            # Echo - should not import
            should_import = should_import_remote_update(ledger, "gcal-1", remote_version=5)
            assert should_import is False


def test_should_import_remote_update_new():
    """Test helper function accepts new entities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # New entity - should import
            should_import = should_import_remote_update(ledger, "gcal-new", remote_version=1)
            assert should_import is True


def test_resolve_conflict_local_wins():
    """Test DoD: Latest-wins conflict resolution (local newer)."""
    local_ts = "2025-10-08T13:00:00+00:00"
    remote_ts = "2025-10-08T12:00:00+00:00"

    winner = resolve_conflict(local_ts, remote_ts)

    assert winner == "local"


def test_resolve_conflict_remote_wins():
    """Test DoD: Latest-wins conflict resolution (remote newer)."""
    local_ts = "2025-10-08T12:00:00+00:00"
    remote_ts = "2025-10-08T13:00:00+00:00"

    winner = resolve_conflict(local_ts, remote_ts)

    assert winner == "remote"


def test_resolve_conflict_tie():
    """Test conflict resolution when timestamps equal."""
    ts = "2025-10-08T12:00:00+00:00"

    winner = resolve_conflict(ts, ts)

    assert winner == "tie"


def test_create_sync_ledger_factory():
    """Test factory function for creating ledger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"

        ledger = create_sync_ledger(vault_path)

        expected_path = vault_path / "artifacts" / "sync_ledger.db"
        assert ledger.db_path == expected_path
        assert expected_path.exists()

        ledger.close()


def test_dod_echo_loop_prevention():
    """Test DoD: Echo-loop test (Kira→GCal→Kira) results in single authoritative write.

    Scenario:
    1. Kira creates event (version 1)
    2. Export to GCal (version 2, record in ledger)
    3. GCal sends update back (still version 2) - should be detected as echo
    4. Result: No duplicate writes
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # Step 1: Kira creates event
            metadata = {"title": "Meeting", "tags": []}
            kira_v1 = create_kira_sync_contract(metadata)
            assert kira_v1["x-kira"]["version"] == 1
            assert kira_v1["x-kira"]["source"] == "kira"

            # Step 2: Export to GCal (assign remote ID, update contract)
            gcal_v2 = create_remote_sync_contract(
                kira_v1,
                source="gcal",
                remote_id="gcal-event-123",
                etag="etag-initial",
            )
            assert gcal_v2["x-kira"]["version"] == 2
            assert gcal_v2["x-kira"]["source"] == "gcal"

            # Record in ledger that we wrote version 2
            ledger.record_sync("gcal-event-123", version=2, etag="etag-initial")

            # Step 3: GCal sends update back (echo of our write)
            remote_version = 2
            remote_etag = "etag-initial"

            # Should detect as echo and NOT import
            should_import = ledger.should_import("gcal-event-123", remote_version, remote_etag)
            assert should_import is False, "Echo loop not detected!"

            # Result: Only one authoritative write (no duplicate)
            assert gcal_v2["x-kira"]["version"] == 2  # Version didn't increment again


def test_dod_echo_loop_with_real_change():
    """Test that real changes after echo are still imported.

    Scenario:
    1. Kira→GCal (version 2)
    2. GCal echoes back (version 2) - ignored
    3. User edits in GCal (version 3) - imported
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # After Kira→GCal export
            ledger.record_sync("gcal-event-1", version=2)

            # Echo comes back (version 2) - ignore
            assert ledger.should_import("gcal-event-1", remote_version=2) is False

            # Real change in GCal (version 3) - import
            assert ledger.should_import("gcal-event-1", remote_version=3) is True


def test_ledger_update_on_reimport():
    """Test ledger updates when we reimport."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # Initial sync
            ledger.record_sync("gcal-1", version=1, entity_id="event-1")

            # Later sync with new version
            ledger.record_sync("gcal-1", version=3, entity_id="event-1")

            # Should reflect latest
            entry = ledger.get_entry("gcal-1")
            assert entry.version_seen == 3


def test_multiple_remote_entities():
    """Test ledger tracks multiple remote entities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            # Track multiple entities
            ledger.record_sync("gcal-event-1", version=1, entity_id="event-a")
            ledger.record_sync("gcal-event-2", version=5, entity_id="event-b")
            ledger.record_sync("gcal-event-3", version=3, entity_id="event-c")

            # Each tracked independently
            assert ledger.get_entry("gcal-event-1").version_seen == 1
            assert ledger.get_entry("gcal-event-2").version_seen == 5
            assert ledger.get_entry("gcal-event-3").version_seen == 3


def test_context_manager():
    """Test ledger context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"

        with SyncLedger(db_path) as ledger:
            ledger.record_sync("test", version=1)

        # Connection should be closed
        assert ledger._conn is None
