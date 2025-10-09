"""Integration tests for clarification queue persistence.

Tests verify:
- Clarification queue survives process restart
- Queue serialization format is correct
- Pending clarifications are restored
"""

import json
from pathlib import Path

import pytest


class TestClarificationQueuePersistence:
    """Test clarification queue persistence."""

    def test_queue_survives_restart(self, tmp_path: Path):
        """Verify clarification queue persists across restarts.

        Scenario:
        1. Create 2 items in queue
        2. Restart (create new queue instance)
        3. Verify items are restored
        """
        from kira.plugins.inbox.clarification_queue import ClarificationQueue

        storage_path = tmp_path / "clarifications.json"

        # First session: create 2 items
        queue1 = ClarificationQueue(storage_path)

        item1 = queue1.add(
            source_event_id="evt-001",
            extracted_type="task",
            extracted_data={"title": "First task", "content": "Do something"},
            confidence=0.65,
        )

        item2 = queue1.add(
            source_event_id="evt-002",
            extracted_type="note",
            extracted_data={"title": "Second note", "content": "Remember this"},
            confidence=0.70,
            alternatives=[{"type": "task", "confidence": 0.5}],
        )

        # Verify items were created
        assert item1.clarification_id.startswith("clarif-")
        assert item2.clarification_id.startswith("clarif-")

        # Simulate restart: create new queue instance
        queue2 = ClarificationQueue(storage_path)

        # Verify items were restored
        pending = queue2.get_pending()
        assert len(pending) == 2

        # Verify data integrity
        ids = {item.clarification_id for item in pending}
        assert item1.clarification_id in ids
        assert item2.clarification_id in ids

        # Verify all fields are preserved
        restored_item1 = next(i for i in pending if i.clarification_id == item1.clarification_id)
        assert restored_item1.source_event_id == "evt-001"
        assert restored_item1.extracted_type == "task"
        assert restored_item1.confidence == 0.65
        assert restored_item1.extracted_data["title"] == "First task"

        restored_item2 = next(i for i in pending if i.clarification_id == item2.clarification_id)
        assert len(restored_item2.suggested_alternatives) == 1
        assert restored_item2.suggested_alternatives[0]["type"] == "task"

    def test_queue_serialization_format(self, tmp_path: Path):
        """Verify queue uses proper JSON serialization."""
        from kira.plugins.inbox.clarification_queue import ClarificationQueue

        storage_path = tmp_path / "clarifications.json"
        queue = ClarificationQueue(storage_path)

        queue.add(
            source_event_id="evt-test",
            extracted_type="meeting",
            extracted_data={"title": "Team sync"},
            confidence=0.8,
        )

        # Verify file exists and has valid JSON
        assert storage_path.exists()

        with open(storage_path) as f:
            data = json.load(f)

        # Verify structure
        assert "version" in data
        assert "items" in data
        assert len(data["items"]) == 1

        item = data["items"][0]
        assert "clarification_id" in item
        assert "source_event_id" in item
        assert "extracted_type" in item
        assert "extracted_data" in item
        assert "confidence" in item
        assert "created_at" in item
        assert "status" in item


pytestmark = pytest.mark.integration

