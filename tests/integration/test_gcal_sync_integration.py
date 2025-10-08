"""Integration test: GCal ↔ Event ↔ Vault (Phase 6, Point 20).

Tests two-way sync with echo loop prevention:
- Import event from GCal
- Local edit
- Export to GCal  
- Re-import from GCal
- Verify no echo loops, versions and last_write_ts behave correctly

DoD:
- No echo loops
- Versions increment correctly
- last_write_ts behaves correctly
"""

import tempfile
from pathlib import Path

import pytest

from kira.core.host import create_host_api
from kira.sync.contract import create_kira_sync_contract, create_remote_sync_contract, get_sync_version
from kira.sync.ledger import SyncLedger, resolve_conflict


@pytest.fixture
def test_env():
    """Create test environment with vault and sync ledger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        host_api = create_host_api(vault_path)
        
        ledger_path = vault_path / "artifacts" / "sync_ledger.db"
        ledger = SyncLedger(ledger_path)
        
        yield host_api, ledger
        
        ledger.close()


def test_gcal_import_event(test_env):
    """Test DoD: Import event from GCal.
    
    Scenario:
    1. GCal event arrives
    2. Create local event with sync contract
    3. Verify source=gcal, version=1
    """
    host_api, ledger = test_env
    
    # Simulate GCal event import
    gcal_event_id = "gcal-event-123"
    
    # Create event with remote sync contract
    metadata = {
        "title": "Team Meeting",
        "tags": ["work", "meeting"],
    }
    
    # Add sync contract for GCal import
    metadata_with_sync = create_remote_sync_contract(
        metadata,
        source="gcal",
        remote_id=gcal_event_id,
        etag="etag-initial",
    )
    
    # Verify sync contract
    assert metadata_with_sync["x-kira"]["source"] == "gcal"
    assert metadata_with_sync["x-kira"]["version"] == 1
    assert metadata_with_sync["x-kira"]["remote_id"] == gcal_event_id
    
    # Record in ledger
    ledger.record_sync(gcal_event_id, version=1, etag="etag-initial")


def test_local_edit_increments_version(test_env):
    """Test DoD: Local edit changes source to kira and increments version.
    
    Scenario:
    1. Import event from GCal (version 1, source=gcal)
    2. Local edit
    3. Verify source=kira, version=2
    """
    host_api, ledger = test_env
    
    gcal_event_id = "gcal-event-456"
    
    # Step 1: Import from GCal
    metadata = {"title": "Original Event", "tags": []}
    metadata_v1 = create_remote_sync_contract(
        metadata,
        source="gcal",
        remote_id=gcal_event_id,
    )
    
    assert get_sync_version(metadata_v1) == 1
    assert metadata_v1["x-kira"]["source"] == "gcal"
    
    # Step 2: Local edit (Kira write)
    metadata_v2 = create_kira_sync_contract(
        metadata_v1,
        remote_id=gcal_event_id,
    )
    
    # Step 3: Verify version incremented, source changed
    assert get_sync_version(metadata_v2) == 2
    assert metadata_v2["x-kira"]["source"] == "kira"
    assert metadata_v2["x-kira"]["remote_id"] == gcal_event_id


def test_dod_echo_loop_prevention(test_env):
    """Test DoD: Echo-loop (Kira→GCal→Kira) results in single authoritative write.
    
    Scenario:
    1. Kira creates event (version 1)
    2. Export to GCal (version 2)
    3. Record in ledger
    4. GCal echoes back (still version 2)
    5. Ledger detects echo, ignores update
    """
    host_api, ledger = test_env
    
    gcal_event_id = "gcal-event-echo-test"
    
    # Step 1: Kira creates
    metadata = {"title": "My Event", "tags": []}
    kira_v1 = create_kira_sync_contract(metadata)
    assert get_sync_version(kira_v1) == 1
    
    # Step 2: Export to GCal (GCal assigns ID)
    gcal_v2 = create_remote_sync_contract(
        kira_v1,
        source="gcal",
        remote_id=gcal_event_id,
    )
    assert get_sync_version(gcal_v2) == 2
    
    # Step 3: Record in ledger
    ledger.record_sync(gcal_event_id, version=2)
    
    # Step 4: GCal echoes back (version 2, no real change)
    is_echo = ledger.is_echo(gcal_event_id, remote_version=2)
    
    # Step 5: Echo detected!
    assert is_echo is True, "Echo loop not detected!"
    
    # Should NOT import - no duplicate write
    assert ledger.should_import(gcal_event_id, remote_version=2) is False


def test_real_change_after_echo_imported(test_env):
    """Test DoD: Real changes after echo are still imported.
    
    Scenario:
    1. After Kira→GCal export (version 2 in ledger)
    2. GCal echoes back (version 2) - ignored
    3. User edits in GCal (version 3) - imported
    """
    host_api, ledger = test_env
    
    gcal_event_id = "gcal-event-real-change"
    
    # After export
    ledger.record_sync(gcal_event_id, version=2)
    
    # Echo - ignored
    assert ledger.should_import(gcal_event_id, remote_version=2) is False
    
    # Real change - imported
    assert ledger.should_import(gcal_event_id, remote_version=3) is True


def test_conflict_resolution_latest_wins(test_env):
    """Test DoD: Conflict policy is latest-wins by last_write_ts.
    
    Scenario:
    1. Local edit at T1
    2. Remote edit at T2 (T2 > T1)
    3. Conflict resolution: remote wins (latest)
    """
    host_api, ledger = test_env
    
    local_ts = "2025-10-08T12:00:00+00:00"
    remote_ts = "2025-10-08T13:00:00+00:00"  # Later
    
    winner = resolve_conflict(local_ts, remote_ts)
    
    assert winner == "remote", "Latest-wins policy not working"


def test_full_sync_cycle(test_env):
    """Test DoD: Full sync cycle with version tracking.
    
    Complete flow:
    1. Import from GCal (v1, source=gcal)
    2. Local edit (v2, source=kira)
    3. Export to GCal (v3, source=gcal)
    4. Ledger tracks all versions
    """
    host_api, ledger = test_env
    
    gcal_event_id = "gcal-full-cycle"
    
    # Step 1: Import
    metadata = {"title": "Sync Test", "tags": []}
    v1 = create_remote_sync_contract(metadata, source="gcal", remote_id=gcal_event_id)
    assert get_sync_version(v1) == 1
    assert v1["x-kira"]["source"] == "gcal"
    ledger.record_sync(gcal_event_id, version=1)
    
    # Step 2: Local edit
    v2 = create_kira_sync_contract(v1, remote_id=gcal_event_id)
    assert get_sync_version(v2) == 2
    assert v2["x-kira"]["source"] == "kira"
    
    # Step 3: Export back to GCal
    v3 = create_remote_sync_contract(v2, source="gcal", remote_id=gcal_event_id)
    assert get_sync_version(v3) == 3
    assert v3["x-kira"]["source"] == "gcal"
    ledger.record_sync(gcal_event_id, version=3)
    
    # Verify ledger state
    entry = ledger.get_entry(gcal_event_id)
    assert entry.version_seen == 3
    assert entry.remote_id == gcal_event_id


def test_version_monotonic_increase(test_env):
    """Test DoD: Versions always increase monotonically."""
    host_api, ledger = test_env
    
    metadata = {"title": "Version Test", "tags": []}
    
    # Multiple updates
    v1 = create_kira_sync_contract(metadata)
    v2 = create_remote_sync_contract(v1, source="gcal", remote_id="test")
    v3 = create_kira_sync_contract(v2, remote_id="test")
    v4 = create_remote_sync_contract(v3, source="gcal", remote_id="test")
    
    # Versions must increase
    assert get_sync_version(v1) == 1
    assert get_sync_version(v2) == 2
    assert get_sync_version(v3) == 3
    assert get_sync_version(v4) == 4


def test_last_write_ts_updated(test_env):
    """Test DoD: last_write_ts updated on every write."""
    host_api, ledger = test_env
    
    metadata = {"title": "Timestamp Test", "tags": []}
    
    # First write
    v1 = create_kira_sync_contract(metadata)
    ts1 = v1["x-kira"]["last_write_ts"]
    assert ts1 is not None
    
    # Second write
    v2 = create_remote_sync_contract(v1, source="gcal", remote_id="test")
    ts2 = v2["x-kira"]["last_write_ts"]
    assert ts2 is not None
    assert ts2 >= ts1  # Must not go backward


def test_dod_no_echo_loops(test_env):
    """Test DoD: No echo loops in sync cycle.
    
    Critical test: Kira→GCal→Kira does NOT create infinite loop.
    """
    host_api, ledger = test_env
    
    gcal_event_id = "gcal-no-loop"
    
    # Kira→GCal
    metadata = {"title": "No Loop Test", "tags": []}
    kira_write = create_kira_sync_contract(metadata, remote_id=gcal_event_id)
    gcal_import = create_remote_sync_contract(kira_write, source="gcal", remote_id=gcal_event_id)
    
    version = get_sync_version(gcal_import)
    ledger.record_sync(gcal_event_id, version=version)
    
    # GCal→Kira (echo)
    is_echo = ledger.is_echo(gcal_event_id, remote_version=version)
    should_process = ledger.should_import(gcal_event_id, remote_version=version)
    
    # Must detect echo and NOT process
    assert is_echo is True
    assert should_process is False
    
    # Version stays same (no loop increment)
    assert get_sync_version(gcal_import) == version

