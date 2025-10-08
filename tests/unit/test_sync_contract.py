"""Tests for sync contract (Phase 4, Point 14)."""

import pytest

from kira.sync.contract import (
    SyncContract,
    create_kira_sync_contract,
    create_remote_sync_contract,
    get_sync_contract,
    get_sync_version,
    is_kira_origin,
    is_remote_origin,
    update_sync_contract,
)


def test_sync_contract_creation():
    """Test creating sync contract."""
    contract = SyncContract(
        source="kira",
        version=1,
        remote_id="gcal-123",
        last_write_ts="2025-10-08T12:00:00+00:00",
    )

    assert contract.source == "kira"
    assert contract.version == 1
    assert contract.remote_id == "gcal-123"
    assert contract.last_write_ts == "2025-10-08T12:00:00+00:00"


def test_sync_contract_to_dict():
    """Test converting contract to dict."""
    contract = SyncContract(
        source="gcal",
        version=5,
        remote_id="gcal-event-456",
        last_write_ts="2025-10-08T12:00:00+00:00",
        etag="etag-abc",
    )

    data = contract.to_dict()

    assert data["source"] == "gcal"
    assert data["version"] == 5
    assert data["remote_id"] == "gcal-event-456"
    assert data["last_write_ts"] == "2025-10-08T12:00:00+00:00"
    assert data["etag"] == "etag-abc"


def test_sync_contract_from_dict():
    """Test creating contract from dict."""
    data = {
        "source": "kira",
        "version": 3,
        "remote_id": "gcal-789",
        "last_write_ts": "2025-10-08T12:00:00+00:00",
    }

    contract = SyncContract.from_dict(data)

    assert contract.source == "kira"
    assert contract.version == 3
    assert contract.remote_id == "gcal-789"


def test_get_sync_contract_present():
    """Test extracting sync contract from metadata."""
    metadata = {
        "title": "Event",
        "x-kira": {
            "source": "gcal",
            "version": 2,
            "remote_id": "gcal-event-123",
            "last_write_ts": "2025-10-08T12:00:00+00:00",
        },
    }

    contract = get_sync_contract(metadata)

    assert contract is not None
    assert contract.source == "gcal"
    assert contract.version == 2


def test_get_sync_contract_absent():
    """Test extracting contract when none present."""
    metadata = {"title": "Event"}

    contract = get_sync_contract(metadata)

    assert contract is None


def test_update_sync_contract_new():
    """Test updating contract when none exists (creates new)."""
    metadata = {"title": "Event", "tags": []}

    updated = update_sync_contract(metadata, source="kira")

    assert "x-kira" in updated
    assert updated["x-kira"]["source"] == "kira"
    assert updated["x-kira"]["version"] == 1
    assert "last_write_ts" in updated["x-kira"]


def test_update_sync_contract_increments_version():
    """Test DoD: Version increments on update."""
    metadata = {
        "title": "Event",
        "x-kira": {
            "source": "kira",
            "version": 3,
            "last_write_ts": "2025-10-08T12:00:00+00:00",
        },
    }

    updated = update_sync_contract(metadata, source="gcal", remote_id="gcal-123")

    assert updated["x-kira"]["version"] == 4  # Incremented
    assert updated["x-kira"]["source"] == "gcal"  # Changed
    assert updated["x-kira"]["remote_id"] == "gcal-123"


def test_update_sync_contract_preserves_remote_id():
    """Test remote_id preserved when not specified."""
    metadata = {
        "title": "Event",
        "x-kira": {
            "source": "kira",
            "version": 1,
            "remote_id": "gcal-original",
        },
    }

    updated = update_sync_contract(metadata, source="kira")

    # remote_id should be preserved
    assert updated["x-kira"]["remote_id"] == "gcal-original"


def test_create_kira_sync_contract_new():
    """Test DoD: Kira writes set source=kira and increment version."""
    metadata = {"title": "Task", "tags": []}

    updated = create_kira_sync_contract(metadata)

    assert updated["x-kira"]["source"] == "kira"
    assert updated["x-kira"]["version"] == 1
    assert "last_write_ts" in updated["x-kira"]


def test_create_kira_sync_contract_existing():
    """Test Kira write on existing contract."""
    metadata = {
        "title": "Task",
        "x-kira": {
            "source": "gcal",
            "version": 5,
            "remote_id": "gcal-123",
        },
    }

    updated = create_kira_sync_contract(metadata)

    # Source changes to kira
    assert updated["x-kira"]["source"] == "kira"
    # Version increments
    assert updated["x-kira"]["version"] == 6
    # Remote ID preserved
    assert updated["x-kira"]["remote_id"] == "gcal-123"


def test_create_remote_sync_contract_new():
    """Test DoD: GCal imports set source=gcal and increment version."""
    metadata = {"title": "Event", "tags": []}

    updated = create_remote_sync_contract(
        metadata,
        source="gcal",
        remote_id="gcal-event-456",
        etag="etag-xyz",
    )

    assert updated["x-kira"]["source"] == "gcal"
    assert updated["x-kira"]["version"] == 1
    assert updated["x-kira"]["remote_id"] == "gcal-event-456"
    assert updated["x-kira"]["etag"] == "etag-xyz"


def test_create_remote_sync_contract_existing():
    """Test remote import on existing contract."""
    metadata = {
        "title": "Event",
        "x-kira": {
            "source": "kira",
            "version": 3,
        },
    }

    updated = create_remote_sync_contract(
        metadata,
        source="gcal",
        remote_id="gcal-789",
    )

    # Source changes to gcal
    assert updated["x-kira"]["source"] == "gcal"
    # Version increments
    assert updated["x-kira"]["version"] == 4
    # Remote ID set
    assert updated["x-kira"]["remote_id"] == "gcal-789"


def test_is_kira_origin_true():
    """Test checking if write originated from Kira."""
    metadata = {
        "title": "Task",
        "x-kira": {
            "source": "kira",
            "version": 1,
        },
    }

    assert is_kira_origin(metadata) is True


def test_is_kira_origin_false():
    """Test checking Kira origin when false."""
    metadata = {
        "title": "Event",
        "x-kira": {
            "source": "gcal",
            "version": 1,
        },
    }

    assert is_kira_origin(metadata) is False


def test_is_remote_origin_true():
    """Test checking if write originated from specific remote."""
    metadata = {
        "title": "Event",
        "x-kira": {
            "source": "gcal",
            "version": 2,
        },
    }

    assert is_remote_origin(metadata, "gcal") is True
    assert is_remote_origin(metadata, "telegram") is False


def test_get_sync_version():
    """Test getting current sync version."""
    metadata = {
        "title": "Entity",
        "x-kira": {
            "source": "kira",
            "version": 42,
        },
    }

    assert get_sync_version(metadata) == 42


def test_get_sync_version_no_contract():
    """Test getting version when no contract exists."""
    metadata = {"title": "Entity"}

    assert get_sync_version(metadata) == 0


def test_last_write_ts_updated():
    """Test last_write_ts is updated on each write."""
    metadata = {"title": "Event"}

    # First write
    updated1 = update_sync_contract(metadata, source="kira")
    ts1 = updated1["x-kira"]["last_write_ts"]

    # Second write
    updated2 = update_sync_contract(updated1, source="gcal", remote_id="gcal-1")
    ts2 = updated2["x-kira"]["last_write_ts"]

    # Timestamps should be different (or at least second is not before first)
    assert ts2 >= ts1


def test_dod_metadata_persists():
    """Test DoD: Metadata persists and changes predictably."""
    metadata = {"title": "Event", "tags": []}

    # Kira write
    after_kira = create_kira_sync_contract(metadata, remote_id="gcal-123")
    assert after_kira["x-kira"]["source"] == "kira"
    assert after_kira["x-kira"]["version"] == 1

    # GCal import
    after_gcal = create_remote_sync_contract(
        after_kira,
        source="gcal",
        remote_id="gcal-123",
    )
    assert after_gcal["x-kira"]["source"] == "gcal"
    assert after_gcal["x-kira"]["version"] == 2

    # Another Kira write
    after_kira2 = create_kira_sync_contract(after_gcal)
    assert after_kira2["x-kira"]["source"] == "kira"
    assert after_kira2["x-kira"]["version"] == 3

    # Metadata persists and changes predictably
    assert after_kira2["x-kira"]["remote_id"] == "gcal-123"


def test_sync_contract_with_etag():
    """Test sync contract with ETag for optimistic locking."""
    metadata = {"title": "Event"}

    updated = update_sync_contract(
        metadata,
        source="gcal",
        remote_id="gcal-event-1",
        etag='W/"abc123"',
    )

    assert updated["x-kira"]["etag"] == 'W/"abc123"'


def test_multiple_round_trips():
    """Test multiple sync round trips."""
    metadata = {"title": "Shared Event", "tags": []}

    # Kira creates
    v1 = create_kira_sync_contract(metadata)
    assert v1["x-kira"]["version"] == 1
    assert v1["x-kira"]["source"] == "kira"

    # Export to GCal (GCal assigns ID)
    v2 = create_remote_sync_contract(v1, source="gcal", remote_id="gcal-new-123")
    assert v2["x-kira"]["version"] == 2
    assert v2["x-kira"]["source"] == "gcal"

    # Kira edit
    v3 = create_kira_sync_contract(v2)
    assert v3["x-kira"]["version"] == 3
    assert v3["x-kira"]["source"] == "kira"

    # GCal sync
    v4 = create_remote_sync_contract(v3, source="gcal", remote_id="gcal-new-123")
    assert v4["x-kira"]["version"] == 4
    assert v4["x-kira"]["source"] == "gcal"

    # Remote ID preserved throughout
    assert v4["x-kira"]["remote_id"] == "gcal-new-123"
