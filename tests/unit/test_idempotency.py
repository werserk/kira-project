"""Tests for event idempotency and deduplication (Phase 2, Point 7)."""

import tempfile
from pathlib import Path

import pytest

from kira.core.idempotency import (
    EventDedupeStore,
    create_dedupe_store,
    generate_event_id,
    normalize_payload_for_hashing,
)


def test_normalize_payload_removes_timing_fields():
    """Test payload normalization removes timing/metadata fields."""
    payload = {
        "message": "test",
        "user": "alice",
        "received_at": "2025-10-08T12:00:00Z",
        "processed_at": "2025-10-08T12:00:01Z",
        "retry_count": 3,
        "trace_id": "abc-123",
    }
    
    normalized = normalize_payload_for_hashing(payload)
    
    # Should not contain timing fields
    assert "received_at" not in normalized
    assert "processed_at" not in normalized
    assert "retry_count" not in normalized
    assert "trace_id" not in normalized
    
    # Should contain logical fields
    assert "message" in normalized
    assert "user" in normalized


def test_normalize_payload_deterministic():
    """Test payload normalization is deterministic."""
    payload1 = {"b": 2, "a": 1, "c": 3}
    payload2 = {"a": 1, "c": 3, "b": 2}  # Different order
    
    norm1 = normalize_payload_for_hashing(payload1)
    norm2 = normalize_payload_for_hashing(payload2)
    
    # Should be identical despite different order
    assert norm1 == norm2


def test_generate_event_id_deterministic():
    """Test event ID generation is deterministic."""
    payload = {"message": "test", "user": "alice"}
    
    id1 = generate_event_id("telegram", "msg-123", payload)
    id2 = generate_event_id("telegram", "msg-123", payload)
    
    # Should be identical
    assert id1 == id2
    assert len(id1) == 64  # SHA-256 hex


def test_generate_event_id_different_for_different_inputs():
    """Test event IDs differ for different inputs."""
    payload = {"message": "test"}
    
    id1 = generate_event_id("telegram", "msg-123", payload)
    id2 = generate_event_id("telegram", "msg-456", payload)  # Different external_id
    id3 = generate_event_id("gcal", "msg-123", payload)  # Different source
    
    assert id1 != id2
    assert id1 != id3
    assert id2 != id3


def test_generate_event_id_ignores_timing_fields():
    """Test event ID ignores timing/metadata fields."""
    payload1 = {
        "message": "test",
        "received_at": "2025-10-08T12:00:00Z",
    }
    payload2 = {
        "message": "test",
        "received_at": "2025-10-08T13:00:00Z",  # Different time
    }
    
    id1 = generate_event_id("telegram", "msg-123", payload1)
    id2 = generate_event_id("telegram", "msg-123", payload2)
    
    # Should be identical (timing field ignored)
    assert id1 == id2


def test_dedupe_store_initialization():
    """Test dedupe store initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        store = EventDedupeStore(db_path)
        
        assert store.db_path == db_path
        assert db_path.exists()
        
        store.close()


def test_dedupe_store_is_duplicate_new_event():
    """Test duplicate check for new event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            event_id = "test-event-123"
            
            # First check - should not be duplicate
            assert store.is_duplicate(event_id) is False


def test_dedupe_store_mark_seen_first_time():
    """Test marking event as seen for first time."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            event_id = "test-event-123"
            
            # Mark as seen
            is_first = store.mark_seen(event_id, source="telegram", external_id="msg-123")
            
            assert is_first is True
            assert store.is_duplicate(event_id) is True


def test_dedupe_store_mark_seen_duplicate():
    """Test marking event as seen when it's a duplicate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            event_id = "test-event-123"
            
            # First time
            is_first1 = store.mark_seen(event_id)
            assert is_first1 is True
            
            # Second time (duplicate)
            is_first2 = store.mark_seen(event_id)
            assert is_first2 is False


def test_dedupe_store_seen_count_increments():
    """Test seen count increments for duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            event_id = "test-event-123"
            
            # Mark as seen 3 times
            store.mark_seen(event_id)
            store.mark_seen(event_id)
            store.mark_seen(event_id)
            
            # Check info
            info = store.get_event_info(event_id)
            assert info is not None
            assert info["seen_count"] == 3


def test_dedupe_store_get_event_info():
    """Test getting event information."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            event_id = "test-event-123"
            metadata = {"key": "value"}
            
            store.mark_seen(
                event_id,
                source="telegram",
                external_id="msg-123",
                metadata=metadata,
            )
            
            info = store.get_event_info(event_id)
            
            assert info is not None
            assert info["event_id"] == event_id
            assert info["source"] == "telegram"
            assert info["external_id"] == "msg-123"
            assert info["seen_count"] == 1
            assert info["metadata"] == metadata
            assert "first_seen_ts" in info
            assert "last_seen_ts" in info


def test_dedupe_store_get_event_info_not_found():
    """Test getting info for non-existent event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            info = store.get_event_info("nonexistent")
            assert info is None


def test_dedupe_store_cleanup_old_events():
    """Test cleanup of old events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            # Insert old event manually
            conn = store._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count)
                VALUES (?, ?, ?, 1)
            """, (
                "old-event",
                "2024-01-01T12:00:00+00:00",  # Old timestamp
                "2024-01-01T12:00:00+00:00",
            ))
            conn.commit()
            
            # Insert recent event
            store.mark_seen("recent-event")
            
            # Cleanup events older than 30 days
            deleted = store.cleanup_old_events(ttl_days=30)
            
            assert deleted == 1
            assert store.is_duplicate("old-event") is False
            assert store.is_duplicate("recent-event") is True


def test_dedupe_store_get_stats():
    """Test getting dedupe store statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            # Add some events
            store.mark_seen("event-1", source="telegram")
            store.mark_seen("event-2", source="telegram")
            store.mark_seen("event-2", source="telegram")  # Duplicate
            store.mark_seen("event-3", source="gcal")
            
            stats = store.get_stats()
            
            assert stats["total_unique_events"] == 3
            assert stats["events_with_duplicates"] == 1  # event-2
            assert stats["total_seen_count"] == 4  # 1+2+1
            assert stats["duplicate_rate"] > 0
            assert stats["by_source"]["telegram"] == 2
            assert stats["by_source"]["gcal"] == 1


def test_dedupe_store_stats_empty():
    """Test statistics for empty store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            stats = store.get_stats()
            
            assert stats["total_unique_events"] == 0
            assert stats["events_with_duplicates"] == 0
            assert stats["total_seen_count"] == 0
            assert stats["duplicate_rate"] == 0.0


def test_create_dedupe_store():
    """Test factory function for creating dedupe store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        
        store = create_dedupe_store(vault_path)
        
        expected_path = vault_path / "artifacts" / "dedupe.db"
        assert store.db_path == expected_path
        assert expected_path.exists()
        
        store.close()


def test_dod_republishing_same_event_is_noop():
    """Test DoD: Re-publishing the same logical event is a no-op."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            # Same logical event
            payload = {"message": "test", "user": "alice"}
            event_id = generate_event_id("telegram", "msg-123", payload)
            
            # First publish
            is_first1 = store.mark_seen(event_id)
            assert is_first1 is True
            
            # Re-publish (should be no-op)
            is_first2 = store.mark_seen(event_id)
            assert is_first2 is False
            
            # Re-publish again (still no-op)
            is_first3 = store.mark_seen(event_id)
            assert is_first3 is False
            
            # Verify seen count
            info = store.get_event_info(event_id)
            assert info["seen_count"] == 3


def test_context_manager():
    """Test dedupe store context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with EventDedupeStore(db_path) as store:
            store.mark_seen("test-event")
        
        # Connection should be closed
        assert store._conn is None


def test_different_sources_different_event_ids():
    """Test that same external_id from different sources produces different event IDs."""
    payload = {"message": "test"}
    
    telegram_id = generate_event_id("telegram", "123", payload)
    gcal_id = generate_event_id("gcal", "123", payload)
    
    assert telegram_id != gcal_id

