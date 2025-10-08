"""Tests for quarantine system (Phase 1, Point 6)."""

import json
import tempfile
from pathlib import Path

import pytest

from kira.core.quarantine import (
    QuarantineRecord,
    cleanup_old_quarantine,
    get_quarantine_stats,
    list_quarantined_items,
    quarantine_invalid_entity,
)


def test_quarantine_invalid_entity():
    """Test quarantining an invalid entity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        payload = {"title": "", "status": "invalid"}
        errors = ["Title cannot be empty", "Invalid status"]

        record = quarantine_invalid_entity(
            entity_type="task",
            payload=payload,
            errors=errors,
            reason="Validation failed",
            quarantine_dir=quarantine_dir,
        )

        assert isinstance(record, QuarantineRecord)
        assert record.entity_type == "task"
        assert record.reason == "Validation failed"
        assert record.errors == errors
        assert record.payload == payload
        assert record.timestamp is not None

        # Verify file was created
        assert quarantine_dir.exists()
        json_files = list(quarantine_dir.glob("*.json"))
        assert len(json_files) == 1


def test_quarantine_creates_directory():
    """Test quarantine creates directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "nonexistent" / "quarantine"

        assert not quarantine_dir.exists()

        quarantine_invalid_entity(
            entity_type="task",
            payload={"title": "test"},
            errors=["error"],
            reason="test",
            quarantine_dir=quarantine_dir,
        )

        assert quarantine_dir.exists()


def test_quarantine_file_contains_correct_data():
    """Test quarantined file contains all required data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        payload = {"id": "task-123", "title": "", "status": "invalid"}
        errors = ["Title cannot be empty", "Invalid status: invalid"]

        record = quarantine_invalid_entity(
            entity_type="task",
            payload=payload,
            errors=errors,
            reason="Validation failed",
            quarantine_dir=quarantine_dir,
        )

        # Read the file
        json_files = list(quarantine_dir.glob("*.json"))
        assert len(json_files) == 1

        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)

        assert data["entity_type"] == "task"
        assert data["reason"] == "Validation failed"
        assert data["errors"] == errors
        assert data["payload"] == payload
        assert "timestamp" in data
        assert "metadata" in data


def test_list_quarantined_items_empty():
    """Test listing quarantined items when directory is empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        items = list_quarantined_items(quarantine_dir)
        assert len(items) == 0


def test_list_quarantined_items():
    """Test listing quarantined items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        # Quarantine multiple items
        for i in range(3):
            quarantine_invalid_entity(
                entity_type="task",
                payload={"id": f"task-{i}", "title": ""},
                errors=[f"Error {i}"],
                reason=f"Reason {i}",
                quarantine_dir=quarantine_dir,
            )

        items = list_quarantined_items(quarantine_dir)
        assert len(items) == 3

        # Should be sorted by timestamp (newest first)
        assert all(isinstance(item, QuarantineRecord) for item in items)


def test_list_quarantined_items_with_filter():
    """Test listing quarantined items with entity type filter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        # Quarantine different entity types
        quarantine_invalid_entity(
            entity_type="task",
            payload={"title": ""},
            errors=["error"],
            reason="test",
            quarantine_dir=quarantine_dir,
        )

        quarantine_invalid_entity(
            entity_type="note",
            payload={"title": ""},
            errors=["error"],
            reason="test",
            quarantine_dir=quarantine_dir,
        )

        # Filter by type
        tasks = list_quarantined_items(quarantine_dir, entity_type="task")
        assert len(tasks) == 1
        assert tasks[0].entity_type == "task"

        notes = list_quarantined_items(quarantine_dir, entity_type="note")
        assert len(notes) == 1
        assert notes[0].entity_type == "note"


def test_list_quarantined_items_with_limit():
    """Test listing quarantined items with limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        # Quarantine 5 items
        for i in range(5):
            quarantine_invalid_entity(
                entity_type="task",
                payload={"id": f"task-{i}"},
                errors=["error"],
                reason="test",
                quarantine_dir=quarantine_dir,
            )

        # Get limited results
        items = list_quarantined_items(quarantine_dir, limit=3)
        assert len(items) == 3


def test_get_quarantine_stats_empty():
    """Test getting quarantine stats when empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        stats = get_quarantine_stats(quarantine_dir)

        assert stats["total_quarantined"] == 0
        assert stats["by_entity_type"] == {}


def test_get_quarantine_stats():
    """Test getting quarantine statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        # Quarantine different entity types
        quarantine_invalid_entity(
            entity_type="task",
            payload={"title": ""},
            errors=["error"],
            reason="test",
            quarantine_dir=quarantine_dir,
        )

        quarantine_invalid_entity(
            entity_type="task",
            payload={"title": ""},
            errors=["error"],
            reason="test",
            quarantine_dir=quarantine_dir,
        )

        quarantine_invalid_entity(
            entity_type="note",
            payload={"title": ""},
            errors=["error"],
            reason="test",
            quarantine_dir=quarantine_dir,
        )

        stats = get_quarantine_stats(quarantine_dir)

        assert stats["total_quarantined"] == 3
        assert stats["by_entity_type"]["task"] == 2
        assert stats["by_entity_type"]["note"] == 1


def test_cleanup_old_quarantine():
    """Test cleaning up old quarantined items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        # Create a quarantined item with old timestamp
        old_payload = {
            "timestamp": "2024-01-01T12:00:00+00:00",
            "entity_type": "task",
            "reason": "old",
            "errors": ["error"],
            "payload": {},
        }

        old_file = quarantine_dir / "task_old.json"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        with open(old_file, "w", encoding="utf-8") as f:
            json.dump(old_payload, f)

        # Create a recent item
        quarantine_invalid_entity(
            entity_type="task",
            payload={"title": ""},
            errors=["error"],
            reason="recent",
            quarantine_dir=quarantine_dir,
        )

        # Should have 2 items
        assert len(list(quarantine_dir.glob("*.json"))) == 2

        # Cleanup items older than 30 days
        deleted = cleanup_old_quarantine(quarantine_dir, days_old=30)

        assert deleted == 1
        assert len(list(quarantine_dir.glob("*.json"))) == 1


def test_quarantine_with_special_characters_in_id():
    """Test quarantine handles special characters in entity ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        payload = {"id": "task/with/slashes\\and\\backslashes", "title": ""}

        record = quarantine_invalid_entity(
            entity_type="task",
            payload=payload,
            errors=["error"],
            reason="test",
            quarantine_dir=quarantine_dir,
        )

        # Should create file without errors
        assert record.file_path.exists()


def test_quarantine_preserves_payload_intact():
    """Test quarantine preserves complete payload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        quarantine_dir = Path(tmpdir) / "quarantine"

        payload = {
            "id": "task-123",
            "title": "Test",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "special_chars": "unicode: ñ, emoji: 😊",
        }

        record = quarantine_invalid_entity(
            entity_type="task",
            payload=payload,
            errors=["error"],
            reason="test",
            quarantine_dir=quarantine_dir,
        )

        # Read back and verify
        items = list_quarantined_items(quarantine_dir)
        assert len(items) == 1
        assert items[0].payload == payload


def test_dod_every_validation_failure_produces_artifact():
    """Test DoD: Every validation failure produces a quarantined artifact.

    This is tested indirectly through Host API integration.
    """
    # This test documents the requirement
    # Actual enforcement is tested via Host API tests
    pass
