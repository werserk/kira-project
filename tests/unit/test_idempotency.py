"""Tests for event idempotency and deduplication (Phase 3, Point 9).

DoD: Re-publishing the same logical event is a no-op (unit + integration).
Tests SHA-256 event ID generation, SQLite dedupe store, and TTL cleanup.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kira.core.idempotency import (
    EventDedupeStore,
    create_dedupe_store,
    generate_event_id,
    normalize_payload_for_hashing,
)


class TestPayloadNormalization:
    """Test payload normalization for consistent hashing."""
    
    def test_normalize_removes_volatile_fields(self):
        """Test normalization removes timing/metadata fields."""
        payload = {
            "message": "Hello",
            "user_id": 123,
            "received_at": "2025-10-08T12:00:00+00:00",
            "processed_at": "2025-10-08T12:00:05+00:00",
            "retry_count": 2,
            "trace_id": "abc-123"
        }
        
        normalized = normalize_payload_for_hashing(payload)
        
        # Should only contain logical fields
        assert "message" in normalized
        assert "user_id" in normalized
        # Volatile fields should be removed
        assert "received_at" not in normalized
        assert "processed_at" not in normalized
        assert "retry_count" not in normalized
        assert "trace_id" not in normalized
    
    def test_normalize_sorts_keys(self):
        """Test normalization produces deterministic JSON."""
        payload1 = {"b": 2, "a": 1, "c": 3}
        payload2 = {"c": 3, "a": 1, "b": 2}
        
        normalized1 = normalize_payload_for_hashing(payload1)
        normalized2 = normalize_payload_for_hashing(payload2)
        
        # Same keys in different order should normalize identically
        assert normalized1 == normalized2
    
    def test_normalize_consistent_separators(self):
        """Test normalization uses consistent JSON separators."""
        payload = {"a": 1, "b": {"c": 2}}
        normalized = normalize_payload_for_hashing(payload)
        
        # Should use compact separators (no spaces)
        assert " " not in normalized


class TestEventIDGeneration:
    """Test deterministic event ID generation (Phase 3, Point 9)."""
    
    def test_generate_event_id_returns_sha256(self):
        """Test event ID is SHA-256 hex (64 chars)."""
        event_id = generate_event_id(
            source="telegram",
            external_id="msg-123",
            payload={"message": "test"}
        )
        
        assert isinstance(event_id, str)
        assert len(event_id) == 64
        # Should be hex
        assert all(c in "0123456789abcdef" for c in event_id)
    
    def test_identical_events_produce_same_id(self):
        """Test same logical event produces same ID (Phase 3, Point 9)."""
        payload = {"message": "Hello", "user_id": 123}
        
        id1 = generate_event_id("telegram", "msg-456", payload.copy())
        id2 = generate_event_id("telegram", "msg-456", payload.copy())
        
        assert id1 == id2
    
    def test_different_payloads_produce_different_ids(self):
        """Test different payloads produce different IDs."""
        id1 = generate_event_id("telegram", "msg-456", {"message": "Hello"})
        id2 = generate_event_id("telegram", "msg-456", {"message": "Goodbye"})
        
        assert id1 != id2
    
    def test_different_sources_produce_different_ids(self):
        """Test different sources produce different IDs."""
        payload = {"message": "Hello"}
        
        id1 = generate_event_id("telegram", "msg-456", payload)
        id2 = generate_event_id("gcal", "msg-456", payload)
        
        assert id1 != id2
    
    def test_different_external_ids_produce_different_ids(self):
        """Test different external IDs produce different IDs."""
        payload = {"message": "Hello"}
        
        id1 = generate_event_id("telegram", "msg-123", payload)
        id2 = generate_event_id("telegram", "msg-456", payload)
        
        assert id1 != id2
    
    def test_payload_with_retry_fields_normalized(self):
        """Test payload with volatile fields produces consistent ID."""
        base_payload = {"message": "Hello", "user_id": 123}
        
        # Same logical payload with different retry metadata
        payload1 = {**base_payload, "retry_count": 0, "trace_id": "abc"}
        payload2 = {**base_payload, "retry_count": 2, "trace_id": "xyz"}
        
        id1 = generate_event_id("telegram", "msg-456", payload1)
        id2 = generate_event_id("telegram", "msg-456", payload2)
        
        # Should produce same ID (volatile fields ignored)
        assert id1 == id2


class TestEventDedupeStore:
    """Test SQLite dedupe store (Phase 3, Point 9)."""
    
    def test_create_dedupe_store(self):
        """Test creating dedupe store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "dedupe.db"
            store = EventDedupeStore(db_path)
            
            assert store.db_path == db_path
            assert db_path.exists()
            
            store.close()
    
    def test_is_duplicate_false_for_new_event(self):
        """Test is_duplicate returns False for new event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            event_id = "abc123"
            assert store.is_duplicate(event_id) is False
            
            store.close()
    
    def test_mark_seen_returns_true_for_new_event(self):
        """Test mark_seen returns True for first occurrence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            event_id = "abc123"
            is_first = store.mark_seen(event_id, source="telegram")
            
            assert is_first is True
            
            store.close()
    
    def test_mark_seen_returns_false_for_duplicate(self):
        """Test mark_seen returns False for duplicate (Phase 3, Point 9 DoD)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            event_id = "abc123"
            
            # First time
            is_first1 = store.mark_seen(event_id, source="telegram")
            assert is_first1 is True
            
            # Second time (duplicate)
            is_first2 = store.mark_seen(event_id, source="telegram")
            assert is_first2 is False
            
            store.close()
    
    def test_is_duplicate_true_after_mark_seen(self):
        """Test is_duplicate returns True after marking seen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            event_id = "abc123"
            store.mark_seen(event_id)
            
            assert store.is_duplicate(event_id) is True
            
            store.close()
    
    def test_get_event_info_none_for_unseen(self):
        """Test get_event_info returns None for unseen event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            info = store.get_event_info("nonexistent")
            assert info is None
            
            store.close()
    
    def test_get_event_info_returns_data_for_seen(self):
        """Test get_event_info returns data for seen event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            event_id = "abc123"
            metadata = {"key": "value"}
            store.mark_seen(
                event_id,
                source="telegram",
                external_id="msg-456",
                metadata=metadata
            )
            
            info = store.get_event_info(event_id)
            
            assert info is not None
            assert info["event_id"] == event_id
            assert info["source"] == "telegram"
            assert info["external_id"] == "msg-456"
            assert info["metadata"] == metadata
            assert info["seen_count"] == 1
            assert "first_seen_ts" in info
            assert "last_seen_ts" in info
            
            store.close()
    
    def test_seen_count_increments_on_duplicates(self):
        """Test seen_count increments for duplicates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            event_id = "abc123"
            
            # Mark seen 3 times
            store.mark_seen(event_id)
            store.mark_seen(event_id)
            store.mark_seen(event_id)
            
            info = store.get_event_info(event_id)
            assert info["seen_count"] == 3
            
            store.close()
    
    def test_last_seen_ts_updates_on_duplicates(self):
        """Test last_seen_ts updates when event seen again."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            event_id = "abc123"
            
            # Mark seen twice
            store.mark_seen(event_id)
            info1 = store.get_event_info(event_id)
            first_seen_1 = info1["first_seen_ts"]
            last_seen_1 = info1["last_seen_ts"]
            
            # Wait a bit and mark seen again
            import time
            time.sleep(0.01)
            
            store.mark_seen(event_id)
            info2 = store.get_event_info(event_id)
            first_seen_2 = info2["first_seen_ts"]
            last_seen_2 = info2["last_seen_ts"]
            
            # first_seen should not change
            assert first_seen_2 == first_seen_1
            # last_seen should be updated
            assert last_seen_2 >= last_seen_1
            
            store.close()


class TestTTLCleanup:
    """Test TTL-based cleanup (Phase 3, Point 9)."""
    
    def test_cleanup_old_events(self):
        """Test cleaning up events older than TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            # Mark some events as seen
            store.mark_seen("event-1")
            store.mark_seen("event-2")
            store.mark_seen("event-3")
            
            # Cleanup with very long TTL (should delete nothing)
            deleted = store.cleanup_old_events(ttl_days=365)
            assert deleted == 0
            
            # All events should still be there
            assert store.is_duplicate("event-1") is True
            assert store.is_duplicate("event-2") is True
            assert store.is_duplicate("event-3") is True
            
            store.close()
    
    def test_cleanup_respects_ttl(self):
        """Test cleanup only removes events older than TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            # Mark event as seen
            event_id = "old-event"
            store.mark_seen(event_id)
            
            # Manually update first_seen_ts to be very old
            conn = store._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE seen_events SET first_seen_ts = ? WHERE event_id = ?",
                ("2020-01-01T00:00:00+00:00", event_id)
            )
            conn.commit()
            
            # Cleanup with short TTL
            deleted = store.cleanup_old_events(ttl_days=1)
            
            # Old event should be deleted
            assert deleted >= 1
            assert store.is_duplicate(event_id) is False
            
            store.close()


class TestDedupeStoreStats:
    """Test dedupe store statistics."""
    
    def test_get_stats_empty_store(self):
        """Test stats for empty store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            stats = store.get_stats()
            
            assert stats["total_unique_events"] == 0
            assert stats["events_with_duplicates"] == 0
            assert stats["total_seen_count"] == 0
            assert stats["duplicate_rate"] == 0.0
            
            store.close()
    
    def test_get_stats_with_events(self):
        """Test stats with events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            # Mark some events
            store.mark_seen("event-1", source="telegram")
            store.mark_seen("event-2", source="telegram")
            store.mark_seen("event-2", source="telegram")  # Duplicate
            store.mark_seen("event-3", source="gcal")
            
            stats = store.get_stats()
            
            assert stats["total_unique_events"] == 3
            assert stats["events_with_duplicates"] == 1  # event-2 seen twice
            assert stats["total_seen_count"] == 4  # 1 + 2 + 1
            assert stats["duplicate_rate"] > 0
            assert "telegram" in stats["by_source"]
            assert "gcal" in stats["by_source"]
            
            store.close()


class TestCreateDedupeStore:
    """Test factory function for dedupe store."""
    
    def test_create_dedupe_store_from_vault_path(self):
        """Test creating dedupe store from vault path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            store = create_dedupe_store(vault_path)
            
            # Should create artifacts/dedupe.db
            expected_path = vault_path / "artifacts" / "dedupe.db"
            assert store.db_path == expected_path
            assert expected_path.exists()
            
            store.close()


class TestDedupeContextManager:
    """Test dedupe store context manager."""
    
    def test_context_manager_closes_connection(self):
        """Test context manager closes connection on exit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "dedupe.db"
            
            with EventDedupeStore(db_path) as store:
                store.mark_seen("event-1")
                assert store._conn is not None
            
            # Connection should be closed after context
            assert store._conn is None


class TestIdempotencyIntegration:
    """Test idempotency integration (Phase 3, Point 9 DoD)."""
    
    def test_republishing_same_event_is_noop(self):
        """Test re-publishing same logical event is a no-op (Phase 3, Point 9 DoD)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            # Same logical event
            source = "telegram"
            external_id = "msg-123"
            payload = {"message": "Hello", "user_id": 456}
            
            # Generate event ID
            event_id = generate_event_id(source, external_id, payload)
            
            # First publish
            is_new1 = store.mark_seen(event_id, source=source, external_id=external_id)
            assert is_new1 is True
            
            # Second publish (same event)
            is_new2 = store.mark_seen(event_id, source=source, external_id=external_id)
            assert is_new2 is False  # No-op (duplicate)
            
            # Third publish (same event)
            is_new3 = store.mark_seen(event_id, source=source, external_id=external_id)
            assert is_new3 is False  # No-op (duplicate)
            
            # Verify seen count
            info = store.get_event_info(event_id)
            assert info["seen_count"] == 3
            
            store.close()
    
    def test_retry_with_different_metadata_is_noop(self):
        """Test retry with different trace_id/retry_count is a no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventDedupeStore(Path(tmpdir) / "dedupe.db")
            
            source = "telegram"
            external_id = "msg-123"
            base_payload = {"message": "Hello", "user_id": 456}
            
            # First attempt
            payload1 = {**base_payload, "retry_count": 0, "trace_id": "abc"}
            event_id1 = generate_event_id(source, external_id, payload1)
            is_new1 = store.mark_seen(event_id1)
            assert is_new1 is True
            
            # Retry with different metadata (but same logical event)
            payload2 = {**base_payload, "retry_count": 1, "trace_id": "xyz"}
            event_id2 = generate_event_id(source, external_id, payload2)
            
            # Should produce same event_id (volatile fields ignored)
            assert event_id2 == event_id1
            
            # Should be treated as duplicate
            is_new2 = store.mark_seen(event_id2)
            assert is_new2 is False
            
            store.close()
