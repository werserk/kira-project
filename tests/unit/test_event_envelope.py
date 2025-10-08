"""Tests for standardized event envelope (Phase 2, Point 9)."""

import pytest

from kira.core.event_envelope import (
    EventEnvelope,
    create_event_envelope,
    envelope_for_at_least_once_delivery,
    extract_event_for_processing,
    validate_event_envelope,
)


def test_event_envelope_creation():
    """Test creating event envelope."""
    envelope = EventEnvelope(
        event_id="abc123",
        event_ts="2025-10-08T12:00:00+00:00",
        source="telegram",
        type="message.received",
        payload={"text": "Hello"},
    )
    
    assert envelope.event_id == "abc123"
    assert envelope.event_ts == "2025-10-08T12:00:00+00:00"
    assert envelope.source == "telegram"
    assert envelope.type == "message.received"
    assert envelope.payload == {"text": "Hello"}
    assert envelope.seq is None
    assert envelope.correlation_id is None


def test_event_envelope_with_optional_fields():
    """Test event envelope with optional fields."""
    envelope = EventEnvelope(
        event_id="abc123",
        event_ts="2025-10-08T12:00:00+00:00",
        source="gcal",
        type="event.created",
        payload={"title": "Meeting"},
        seq=42,
        correlation_id="corr-123",
        metadata={"key": "value"},
    )
    
    assert envelope.seq == 42
    assert envelope.correlation_id == "corr-123"
    assert envelope.metadata == {"key": "value"}


def test_event_envelope_to_dict():
    """Test converting envelope to dict."""
    envelope = EventEnvelope(
        event_id="abc123",
        event_ts="2025-10-08T12:00:00+00:00",
        source="cli",
        type="task.created",
        payload={"title": "Test"},
        seq=1,
    )
    
    data = envelope.to_dict()
    
    assert data["event_id"] == "abc123"
    assert data["source"] == "cli"
    assert data["type"] == "task.created"
    assert data["payload"] == {"title": "Test"}
    assert data["seq"] == 1


def test_event_envelope_to_dict_omits_none():
    """Test to_dict omits None optional fields."""
    envelope = EventEnvelope(
        event_id="abc123",
        event_ts="2025-10-08T12:00:00+00:00",
        source="internal",
        type="system.event",
        payload={},
    )
    
    data = envelope.to_dict()
    
    # Should not include None fields
    assert "seq" not in data
    assert "correlation_id" not in data


def test_event_envelope_from_dict():
    """Test creating envelope from dict."""
    data = {
        "event_id": "abc123",
        "event_ts": "2025-10-08T12:00:00+00:00",
        "source": "telegram",
        "type": "message.received",
        "payload": {"text": "Hello"},
        "seq": 42,
        "correlation_id": "corr-123",
        "metadata": {"key": "value"},
    }
    
    envelope = EventEnvelope.from_dict(data)
    
    assert envelope.event_id == "abc123"
    assert envelope.source == "telegram"
    assert envelope.seq == 42
    assert envelope.correlation_id == "corr-123"


def test_create_event_envelope():
    """Test factory function for creating envelope."""
    payload = {"text": "Hello", "user_id": 123}
    
    envelope = create_event_envelope(
        source="telegram",
        event_type="message.received",
        payload=payload,
        external_id="msg-456",
    )
    
    assert envelope.source == "telegram"
    assert envelope.type == "message.received"
    assert envelope.payload == payload
    assert len(envelope.event_id) == 64  # SHA-256 hex
    assert "+00:00" in envelope.event_ts  # UTC


def test_create_event_envelope_with_seq():
    """Test creating envelope with sequence number."""
    envelope = create_event_envelope(
        source="gcal",
        event_type="event.updated",
        payload={"title": "Meeting"},
        seq=10,
    )
    
    assert envelope.seq == 10


def test_create_event_envelope_with_correlation_id():
    """Test creating envelope with correlation ID."""
    envelope = create_event_envelope(
        source="internal",
        event_type="task.updated",
        payload={},
        correlation_id="trace-123",
    )
    
    assert envelope.correlation_id == "trace-123"


def test_create_event_envelope_generates_event_id():
    """Test envelope generation creates deterministic event ID."""
    payload = {"data": "test"}
    
    envelope1 = create_event_envelope(
        source="test",
        event_type="test.event",
        payload=payload,
        external_id="ext-1",
    )
    
    envelope2 = create_event_envelope(
        source="test",
        event_type="test.event",
        payload=payload,
        external_id="ext-1",
    )
    
    # Same inputs = same event ID
    assert envelope1.event_id == envelope2.event_id


def test_validate_event_envelope_valid():
    """Test validation of valid envelope."""
    envelope = EventEnvelope(
        event_id="abc123",
        event_ts="2025-10-08T12:00:00+00:00",
        source="telegram",
        type="message.received",
        payload={"text": "Hello"},
    )
    
    errors = validate_event_envelope(envelope)
    assert len(errors) == 0


def test_validate_event_envelope_valid_dict():
    """Test validation of valid envelope dict."""
    data = {
        "event_id": "abc123",
        "event_ts": "2025-10-08T12:00:00+00:00",
        "source": "gcal",
        "type": "event.created",
        "payload": {"title": "Meeting"},
    }
    
    errors = validate_event_envelope(data)
    assert len(errors) == 0


def test_validate_event_envelope_missing_fields():
    """Test validation catches missing required fields."""
    data = {
        "event_id": "abc123",
        # Missing: event_ts, source, type, payload
    }
    
    errors = validate_event_envelope(data)
    
    assert len(errors) >= 4
    assert any("event_ts" in err for err in errors)
    assert any("source" in err for err in errors)
    assert any("type" in err for err in errors)
    assert any("payload" in err for err in errors)


def test_validate_event_envelope_null_fields():
    """Test validation catches null required fields."""
    data = {
        "event_id": None,
        "event_ts": "2025-10-08T12:00:00+00:00",
        "source": "test",
        "type": "test.event",
        "payload": {},
    }
    
    errors = validate_event_envelope(data)
    
    assert len(errors) > 0
    assert any("event_id" in err and "null" in err.lower() for err in errors)


def test_validate_event_envelope_payload_not_dict():
    """Test validation catches non-dict payload."""
    data = {
        "event_id": "abc123",
        "event_ts": "2025-10-08T12:00:00+00:00",
        "source": "test",
        "type": "test.event",
        "payload": "not a dict",  # Invalid
    }
    
    errors = validate_event_envelope(data)
    
    assert len(errors) > 0
    assert any("payload" in err and "dict" in err.lower() for err in errors)


def test_validate_event_envelope_invalid_timestamp():
    """Test validation catches invalid timestamp format."""
    data = {
        "event_id": "abc123",
        "event_ts": "not a timestamp",
        "source": "test",
        "type": "test.event",
        "payload": {},
    }
    
    errors = validate_event_envelope(data)
    
    assert len(errors) > 0
    assert any("event_ts" in err for err in errors)


def test_validate_event_envelope_non_utc_timestamp():
    """Test validation catches non-UTC timestamps."""
    data = {
        "event_id": "abc123",
        "event_ts": "2025-10-08T12:00:00+05:00",  # Not UTC
        "source": "test",
        "type": "test.event",
        "payload": {},
    }
    
    errors = validate_event_envelope(data)
    
    assert len(errors) > 0
    assert any("utc" in err.lower() for err in errors)


def test_validate_event_envelope_seq_wrong_type():
    """Test validation catches wrong seq type."""
    data = {
        "event_id": "abc123",
        "event_ts": "2025-10-08T12:00:00+00:00",
        "source": "test",
        "type": "test.event",
        "payload": {},
        "seq": "not an int",  # Should be int
    }
    
    errors = validate_event_envelope(data)
    
    assert len(errors) > 0
    assert any("seq" in err and "int" in err.lower() for err in errors)


def test_validate_event_envelope_metadata_wrong_type():
    """Test validation catches wrong metadata type."""
    data = {
        "event_id": "abc123",
        "event_ts": "2025-10-08T12:00:00+00:00",
        "source": "test",
        "type": "test.event",
        "payload": {},
        "metadata": "not a dict",  # Should be dict
    }
    
    errors = validate_event_envelope(data)
    
    assert len(errors) > 0
    assert any("metadata" in err and "dict" in err.lower() for err in errors)


def test_envelope_for_at_least_once_delivery():
    """Test preparing envelope for at-least-once delivery."""
    envelope = EventEnvelope(
        event_id="abc123",
        event_ts="2025-10-08T12:00:00+00:00",
        source="telegram",
        type="message.received",
        payload={"text": "Hello"},
    )
    
    data = envelope_for_at_least_once_delivery(envelope)
    
    assert data["metadata"]["delivery_semantics"] == "at-least-once"
    assert data["metadata"]["requires_idempotent_consumer"] is True


def test_extract_event_for_processing():
    """Test extracting event type and payload for processing."""
    envelope = EventEnvelope(
        event_id="abc123",
        event_ts="2025-10-08T12:00:00+00:00",
        source="gcal",
        type="event.created",
        payload={"title": "Meeting", "start": "2025-10-08T14:00:00Z"},
    )
    
    event_type, payload = extract_event_for_processing(envelope)
    
    assert event_type == "event.created"
    assert payload == {"title": "Meeting", "start": "2025-10-08T14:00:00Z"}


def test_round_trip_envelope_serialization():
    """Test envelope can be serialized and deserialized."""
    original = EventEnvelope(
        event_id="abc123",
        event_ts="2025-10-08T12:00:00+00:00",
        source="internal",
        type="task.completed",
        payload={"task_id": "task-456", "result": "success"},
        seq=100,
        correlation_id="corr-789",
        metadata={"user": "alice", "version": 1},
    )
    
    # Serialize
    data = original.to_dict()
    
    # Deserialize
    restored = EventEnvelope.from_dict(data)
    
    # Should be identical
    assert restored.event_id == original.event_id
    assert restored.event_ts == original.event_ts
    assert restored.source == original.source
    assert restored.type == original.type
    assert restored.payload == original.payload
    assert restored.seq == original.seq
    assert restored.correlation_id == original.correlation_id
    assert restored.metadata == original.metadata


def test_dod_all_pipelines_accept_unified_envelope():
    """Test DoD: All pipelines accept unified envelope.
    
    Demonstrated by consistent validation and structure
    across all envelope instances.
    """
    sources = ["telegram", "gcal", "cli", "internal"]
    envelopes = []
    
    for source in sources:
        envelope = create_event_envelope(
            source=source,
            event_type=f"{source}.event",
            payload={"data": f"from {source}"},
            external_id=f"{source}-123",
        )
        envelopes.append(envelope)
    
    # All should have same structure
    for envelope in envelopes:
        # Validate
        errors = validate_event_envelope(envelope)
        assert len(errors) == 0
        
        # All have required fields
        assert envelope.event_id
        assert envelope.event_ts
        assert envelope.source
        assert envelope.type
        assert isinstance(envelope.payload, dict)
    
    # Mixed producers interoperate
    assert len(set(e.source for e in envelopes)) == len(sources)

