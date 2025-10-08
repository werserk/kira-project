"""Integration tests for Google Calendar adapter.

Tests verify:
- GCal import-only mode (no duplicates, timezone correctness, x-kira metadata)
- GCal two-way sync (echo-break, conflict resolution, version management)
- Sync ledger tracking
"""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kira.adapters.gcal.adapter import GCalAdapter, GCalAdapterConfig
from kira.core.host import create_host_api
from kira.sync.contract import create_kira_sync_contract, create_remote_sync_contract, get_sync_version
from kira.sync.ledger import SyncLedger, resolve_conflict, should_import_remote_update


@pytest.fixture
def test_gcal_env():
    """Create test environment with GCal adapter and sync ledger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        host_api = create_host_api(vault_path)

        ledger_path = vault_path / "artifacts" / "sync_ledger.db"
        ledger = SyncLedger(ledger_path)

        config = GCalAdapterConfig(
            calendar_id="test-calendar",
            log_path=vault_path / "logs" / "gcal.jsonl",
        )
        adapter = GCalAdapter(config)

        yield host_api, ledger, adapter

        ledger.close()


class TestGCalImportMode:
    """Test GCal import-only mode (no duplicates, TZ correct, x-kira metadata)."""

    def test_import_only_mode_no_duplicates(self, test_gcal_env):
        """GCal import creates event with x-kira metadata, no duplicates on re-import.

        Scenario:
        1. Import GCal event with remote_id=gcal-123
        2. Record in ledger
        3. Import same event again
        4. Verify ledger prevents duplicate
        """
        host_api, ledger, _adapter = test_gcal_env

        gcal_event_id = "gcal-event-import-test"

        # Step 1: First import from GCal
        metadata = {
            "title": "Team Standup",
            "start_time": datetime.now(UTC).isoformat(),
            "end_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "tags": ["work"],
        }

        # Create with remote sync contract (x-kira metadata)
        metadata_v1 = create_remote_sync_contract(
            metadata,
            source="gcal",
            remote_id=gcal_event_id,
            etag="etag-v1",
        )

        # Verify x-kira metadata
        assert "x-kira" in metadata_v1
        assert metadata_v1["x-kira"]["source"] == "gcal"
        assert metadata_v1["x-kira"]["remote_id"] == gcal_event_id
        assert metadata_v1["x-kira"]["version"] == 1
        assert "last_write_ts" in metadata_v1["x-kira"]

        # Create event in vault
        entity = host_api.create_entity("event", metadata_v1)
        entity_id = entity.id

        # Step 2: Record in ledger
        ledger.record_sync(
            remote_id=gcal_event_id,
            version=1,
            etag="etag-v1",
            entity_id=entity_id,
        )

        # Step 3: Attempt re-import (same version)
        should_import = ledger.should_import(gcal_event_id, remote_version=1, remote_etag="etag-v1")

        # Step 4: Verify no duplicate import
        assert should_import is False, "Ledger should prevent duplicate import"

        # Verify only one event exists
        events = list(host_api.list_entities("event"))
        assert len(events) == 1

    def test_import_timezone_correctness(self, test_gcal_env):
        """GCal import preserves UTC timestamps correctly.

        Scenario:
        1. Import GCal event with specific UTC timestamp
        2. Verify stored timestamp is in UTC
        3. Verify no timezone conversion errors
        """
        host_api, ledger, _adapter = test_gcal_env

        # Create event with explicit UTC timestamp
        start_utc = datetime(2025, 10, 15, 14, 30, 0, tzinfo=UTC)
        end_utc = datetime(2025, 10, 15, 15, 30, 0, tzinfo=UTC)

        metadata = {
            "title": "Timezone Test Event",
            "start_time": start_utc.isoformat(),
            "end_time": end_utc.isoformat(),
            "tags": ["test"],
        }

        metadata_synced = create_remote_sync_contract(
            metadata,
            source="gcal",
            remote_id="gcal-tz-test",
            etag="etag-tz",
        )

        # Create event
        entity = host_api.create_entity("event", metadata_synced)

        # Verify timestamps are preserved in UTC
        assert entity.metadata["start_time"] == start_utc.isoformat()
        assert entity.metadata["end_time"] == end_utc.isoformat()

        # Verify x-kira metadata includes correct last_write_ts
        last_write_ts_str = entity.metadata["x-kira"]["last_write_ts"]
        last_write_ts = datetime.fromisoformat(last_write_ts_str.replace("Z", "+00:00"))

        # Should be recent and in UTC
        assert last_write_ts.tzinfo == UTC
        assert abs((datetime.now(UTC) - last_write_ts).total_seconds()) < 5

        # Record in ledger
        ledger.record_sync("gcal-tz-test", version=1, etag="etag-tz", entity_id=entity.id)

    def test_ledger_tracking(self, test_gcal_env):
        """Ledger tracks remote_id→version_seen/etag for import deduplication.

        Scenario:
        1. Import event with version 1
        2. Check ledger has recorded version
        3. Import same event with version 2 (actual change)
        4. Verify ledger allows import
        """
        _host_api, ledger, _adapter = test_gcal_env

        gcal_event_id = "gcal-ledger-test"

        # Step 1: Record version 1
        ledger.record_sync(gcal_event_id, version=1, etag="etag-v1")

        # Step 2: Verify version recorded
        entry = ledger.get_entry(gcal_event_id)
        assert entry is not None
        assert entry.version_seen == 1
        assert entry.etag_seen == "etag-v1"

        # Step 3: Check if version 2 should be imported (actual change)
        should_import_v2 = ledger.should_import(gcal_event_id, remote_version=2, remote_etag="etag-v2")

        # Step 4: Verify import allowed for new version
        assert should_import_v2 is True, "Ledger should allow import of new version"

        # Update ledger
        ledger.record_sync(gcal_event_id, version=2, etag="etag-v2")

        # Verify updated
        entry_updated = ledger.get_entry(gcal_event_id)
        assert entry_updated.version_seen == 2
        assert entry_updated.etag_seen == "etag-v2"


class TestGCalTwoWaySync:
    """Test GCal two-way sync with echo-break and conflict resolution."""

    def test_echo_break(self, test_gcal_env):
        """Kira→GCal→Kira test yields single authoritative state, no echo loops.

        Scenario:
        1. Kira writes event (version 1, source=kira)
        2. Export to GCal (version 2, source=kira)
        3. Record export in ledger
        4. GCal echoes back (version 2, no change)
        5. Verify echo detected, no re-import
        """
        host_api, ledger, _adapter = test_gcal_env

        gcal_event_id = "gcal-echo-test"

        # Step 1: Kira creates event
        metadata = {
            "title": "My Meeting",
            "start_time": datetime.now(UTC).isoformat(),
            "end_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "tags": ["personal"],
        }

        metadata_v1 = create_kira_sync_contract(metadata)
        entity = host_api.create_entity("event", metadata_v1)

        assert get_sync_version(metadata_v1) == 1
        assert metadata_v1["x-kira"]["source"] == "kira"

        # Step 2: Export to GCal (simulate GCal assigning ID and incrementing version)
        metadata_v2 = create_kira_sync_contract(
            metadata_v1,
            remote_id=gcal_event_id,
        )
        assert get_sync_version(metadata_v2) == 2

        # Update entity
        host_api.update_entity(entity.id, metadata_v2)

        # Step 3: Record export in ledger
        ledger.record_sync(
            remote_id=gcal_event_id,
            version=2,
            etag="etag-export-v2",
            entity_id=entity.id,
        )

        # Step 4: GCal echoes back (same version, no actual change)
        is_echo = ledger.is_echo(gcal_event_id, remote_version=2)
        should_import = ledger.should_import(gcal_event_id, remote_version=2, remote_etag="etag-export-v2")

        # Step 5: Verify echo detected
        assert is_echo is True, "Echo loop not detected!"
        assert should_import is False, "Echo should not be imported!"

        # Verify only one event exists (no duplicate)
        events = list(host_api.list_entities("event"))
        assert len(events) == 1

    def test_conflict_resolution_latest_wins(self, test_gcal_env):
        """Conflicts resolved by latest(last_write_ts).

        Scenario:
        1. Event in Vault: last_write_ts = T1
        2. Event in GCal: last_write_ts = T2 (later)
        3. Resolve conflict
        4. Verify GCal version wins (T2 > T1)
        """
        host_api, _ledger, _adapter = test_gcal_env

        # Create vault entity with earlier timestamp
        t1 = datetime.now(UTC) - timedelta(minutes=10)
        vault_metadata = {
            "title": "Vault Version",
            "start_time": datetime.now(UTC).isoformat(),
            "tags": ["vault"],
            "x-kira": {
                "source": "kira",
                "version": 1,
                "last_write_ts": t1.isoformat(),
            },
        }
        vault_entity = host_api.create_entity("event", vault_metadata)

        # Simulate GCal version with later timestamp (ensure later than t1)
        t2 = datetime.now(UTC) + timedelta(seconds=1)
        gcal_metadata = {
            "title": "GCal Version (Newer)",
            "start_time": datetime.now(UTC).isoformat(),
            "tags": ["gcal"],
            "x-kira": {
                "source": "gcal",
                "version": 2,
                "last_write_ts": t2.isoformat(),
                "remote_id": "gcal-conflict-test",
            },
        }

        # Resolve conflict
        resolution = resolve_conflict(
            local_last_write_ts=vault_metadata["x-kira"]["last_write_ts"],
            remote_last_write_ts=gcal_metadata["x-kira"]["last_write_ts"],
        )

        # Verify GCal version wins (latest timestamp)
        assert resolution == "remote", f"Expected 'remote' to win, got '{resolution}'"
        assert gcal_metadata["x-kira"]["last_write_ts"] > vault_metadata["x-kira"]["last_write_ts"]

    def test_kira_writes_increment_version(self, test_gcal_env):
        """Kira writes increment version when pushing to GCal.

        Scenario:
        1. Import event from GCal (version 1)
        2. Kira edits event
        3. Verify version incremented to 2
        4. Push to GCal
        5. Verify version is 3
        """
        host_api, ledger, _adapter = test_gcal_env

        gcal_event_id = "gcal-version-test"

        # Step 1: Import from GCal (version 1)
        metadata = {
            "title": "Original",
            "start_time": datetime.now(UTC).isoformat(),
            "tags": [],
        }
        metadata_v1 = create_remote_sync_contract(
            metadata,
            source="gcal",
            remote_id=gcal_event_id,
        )
        entity = host_api.create_entity("event", metadata_v1)

        assert get_sync_version(metadata_v1) == 1

        # Record in ledger
        ledger.record_sync(gcal_event_id, version=1, entity_id=entity.id)

        # Step 2: Kira edits event
        metadata_v2 = create_kira_sync_contract(
            metadata_v1,
            remote_id=gcal_event_id,
        )
        metadata_v2["title"] = "Edited by Kira"

        # Step 3: Verify version incremented
        assert get_sync_version(metadata_v2) == 2
        assert metadata_v2["x-kira"]["source"] == "kira"

        # Update entity
        updated_entity = host_api.update_entity(entity.id, metadata_v2)

        # Step 4: Push to GCal (would increment version again in real scenario)
        metadata_v3 = create_kira_sync_contract(
            metadata_v2,
            remote_id=gcal_event_id,
        )

        # Step 5: Verify version is 3
        assert get_sync_version(metadata_v3) == 3

        # Update final version
        host_api.update_entity(updated_entity.id, metadata_v3)

        # Record final push
        ledger.record_sync(gcal_event_id, version=3, entity_id=entity.id)

    def test_round_trip_yields_authoritative_state(self, test_gcal_env):
        """Full Kira→GCal→Kira round-trip yields single authoritative state.

        Scenario:
        1. Kira creates event
        2. Push to GCal
        3. GCal modifies and echoes back
        4. Verify single authoritative state (no duplicates)
        """
        host_api, ledger, _adapter = test_gcal_env

        gcal_event_id = "gcal-roundtrip-test"

        # Step 1: Kira creates event
        metadata = {
            "title": "Round Trip Event",
            "start_time": datetime.now(UTC).isoformat(),
            "end_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "tags": ["test"],
        }
        metadata_v1 = create_kira_sync_contract(metadata)
        entity = host_api.create_entity("event", metadata_v1)

        # Step 2: Push to GCal (assign remote_id)
        metadata_v2 = create_kira_sync_contract(
            metadata_v1,
            remote_id=gcal_event_id,
        )
        host_api.update_entity(entity.id, metadata_v2)
        ledger.record_sync(gcal_event_id, version=2, entity_id=entity.id)

        # Step 3: GCal echoes back (same version = echo)
        should_import = should_import_remote_update(
            ledger=ledger,
            remote_id=gcal_event_id,
            remote_version=2,
        )

        # Step 4: Verify no import (echo detected)
        assert should_import is False, "Echo should be ignored"

        # Verify single event exists
        events = list(host_api.list_entities("event"))
        assert len(events) == 1
        assert events[0].id == entity.id


class TestGCalAcceptance:
    """Acceptance tests for GCal integration."""

    def test_acceptance_import_mode(self, test_gcal_env):
        """GCal import-only mode works end-to-end."""
        host_api, ledger, _adapter = test_gcal_env

        # Import multiple events
        for i in range(3):
            gcal_id = f"gcal-event-{i}"
            metadata = {
                "title": f"Event {i}",
                "start_time": (datetime.now(UTC) + timedelta(hours=i)).isoformat(),
                "tags": ["imported"],
            }

            metadata_synced = create_remote_sync_contract(
                metadata,
                source="gcal",
                remote_id=gcal_id,
            )

            entity = host_api.create_entity("event", metadata_synced)
            ledger.record_sync(gcal_id, version=1, entity_id=entity.id)

        # Verify all imported
        events = list(host_api.list_entities("event"))
        assert len(events) == 3

        # Verify no duplicates on re-import
        for i in range(3):
            gcal_id = f"gcal-event-{i}"
            should_import = ledger.should_import(gcal_id, remote_version=1)
            assert should_import is False

        # All events have x-kira metadata
        for event in events:
            assert "x-kira" in event.metadata
            assert event.metadata["x-kira"]["source"] == "gcal"


pytestmark = pytest.mark.integration

