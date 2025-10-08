"""Tests for standard event envelope (Phase 3, Point 8).

DoD: Pipelines accept the unified envelope.
Tests envelope structure, validation, and at-least-once delivery semantics.
"""

from __future__ import annotations

import pytest

from kira.core.event_envelope import (
    EventEnvelope,
    create_event_envelope,
    envelope_for_at_least_once_delivery,
    extract_event_for_processing,
    validate_event_envelope,
)


class TestEventEnvelopeStructure:
    """Test standard event envelope structure (Phase 3, Point 8)."""

    def test_create_event_envelope_basic(self):
        """Test creating basic event envelope."""
        payload = {"message": "Hello", "user_id": 123}
        envelope = create_event_envelope(
            source="telegram", event_type="message.received", payload=payload, external_id="msg-456"
        )

        assert envelope.source == "telegram"
        assert envelope.type == "message.received"
        assert envelope.payload == payload
        assert envelope.event_id is not None
        assert len(envelope.event_id) == 64  # SHA-256 hex
        assert envelope.event_ts.endswith("+00:00") or envelope.event_ts.endswith("Z")

    def test_create_event_envelope_with_seq(self):
        """Test envelope with sequence number."""
        envelope = create_event_envelope(
            source="gcal", event_type="event.created", payload={"title": "Meeting"}, external_id="evt-789", seq=42
        )

        assert envelope.seq == 42

    def test_create_event_envelope_with_correlation_id(self):
        """Test envelope with correlation ID for tracing."""
        correlation_id = "trace-abc-123"
        envelope = create_event_envelope(
            source="cli", event_type="task.created", payload={"title": "Task"}, correlation_id=correlation_id
        )

        assert envelope.correlation_id == correlation_id

    def test_create_event_envelope_with_metadata(self):
        """Test envelope with additional metadata."""
        metadata = {"priority": "high", "tags": ["urgent"]}
        envelope = create_event_envelope(
            source="internal", event_type="alert.triggered", payload={"alert": "System overload"}, metadata=metadata
        )

        assert envelope.metadata == metadata


class TestEventEnvelopeSerialization:
    """Test envelope serialization/deserialization."""

    def test_to_dict(self):
        """Test converting envelope to dict."""
        envelope = create_event_envelope(
            source="telegram", event_type="message.received", payload={"text": "test"}, external_id="msg-1", seq=1
        )

        data = envelope.to_dict()

        assert "event_id" in data
        assert "event_ts" in data
        assert "source" in data
        assert "type" in data
        assert "payload" in data
        assert data["seq"] == 1
        assert data["source"] == "telegram"
        assert data["type"] == "message.received"

    def test_from_dict(self):
        """Test creating envelope from dict."""
        data = {
            "event_id": "abc123",
            "event_ts": "2025-10-08T12:00:00+00:00",
            "source": "gcal",
            "type": "event.updated",
            "payload": {"title": "Updated Meeting"},
            "seq": 5,
            "correlation_id": "trace-xyz",
        }

        envelope = EventEnvelope.from_dict(data)

        assert envelope.event_id == "abc123"
        assert envelope.source == "gcal"
        assert envelope.type == "event.updated"
        assert envelope.seq == 5
        assert envelope.correlation_id == "trace-xyz"

    def test_round_trip_serialization(self):
        """Test envelope round-trip (to_dict → from_dict)."""
        original = create_event_envelope(
            source="cli",
            event_type="task.updated",
            payload={"id": "task-001", "status": "done"},
            external_id="task-001",
            seq=10,
            correlation_id="trace-123",
            metadata={"user": "alice"},
        )

        data = original.to_dict()
        restored = EventEnvelope.from_dict(data)

        assert restored.event_id == original.event_id
        assert restored.event_ts == original.event_ts
        assert restored.source == original.source
        assert restored.type == original.type
        assert restored.payload == original.payload
        assert restored.seq == original.seq
        assert restored.correlation_id == original.correlation_id
        assert restored.metadata == original.metadata


class TestEventEnvelopeValidation:
    """Test envelope validation (Phase 3, Point 8)."""

    def test_validate_valid_envelope(self):
        """Test validating valid envelope."""
        envelope = create_event_envelope(
            source="telegram", event_type="message.received", payload={"text": "hello"}, external_id="msg-1"
        )

        errors = validate_event_envelope(envelope)
        assert len(errors) == 0

    def test_validate_missing_required_fields(self):
        """Test validation catches missing required fields."""
        data = {
            "event_id": "abc123",
            "source": "telegram",
            # Missing: event_ts, type, payload
        }

        errors = validate_event_envelope(data)

        assert len(errors) >= 2  # At least type and payload missing
        assert any("event_ts" in err for err in errors)
        assert any("type" in err for err in errors)
        assert any("payload" in err for err in errors)

    def test_validate_null_required_fields(self):
        """Test validation catches null required fields."""
        data = {
            "event_id": None,
            "event_ts": "2025-10-08T12:00:00+00:00",
            "source": "telegram",
            "type": None,
            "payload": {"text": "test"},
        }

        errors = validate_event_envelope(data)

        assert any("event_id" in err and "null" in err for err in errors)
        assert any("type" in err and "null" in err for err in errors)

    def test_validate_invalid_payload_type(self):
        """Test validation catches non-dict payload."""
        data = {
            "event_id": "abc123",
            "event_ts": "2025-10-08T12:00:00+00:00",
            "source": "telegram",
            "type": "message.received",
            "payload": "not a dict",  # Should be dict
        }

        errors = validate_event_envelope(data)

        assert any("payload" in err and "dict" in err for err in errors)

    def test_validate_invalid_timestamp_format(self):
        """Test validation catches invalid timestamp."""
        data = {
            "event_id": "abc123",
            "event_ts": "invalid-timestamp",
            "source": "telegram",
            "type": "message.received",
            "payload": {"text": "test"},
        }

        errors = validate_event_envelope(data)

        assert any("event_ts" in err for err in errors)

    def test_validate_non_utc_timestamp(self):
        """Test validation catches non-UTC timestamp."""
        data = {
            "event_id": "abc123",
            "event_ts": "2025-10-08T12:00:00+02:00",  # Not UTC
            "source": "telegram",
            "type": "message.received",
            "payload": {"text": "test"},
        }

        errors = validate_event_envelope(data)

        assert any("UTC" in err for err in errors)

    def test_validate_invalid_seq_type(self):
        """Test validation catches non-int seq."""
        data = {
            "event_id": "abc123",
            "event_ts": "2025-10-08T12:00:00+00:00",
            "source": "telegram",
            "type": "message.received",
            "payload": {"text": "test"},
            "seq": "not an int",
        }

        errors = validate_event_envelope(data)

        assert any("seq" in err and "int" in err for err in errors)

    def test_validate_invalid_metadata_type(self):
        """Test validation catches non-dict metadata."""
        data = {
            "event_id": "abc123",
            "event_ts": "2025-10-08T12:00:00+00:00",
            "source": "telegram",
            "type": "message.received",
            "payload": {"text": "test"},
            "metadata": "not a dict",
        }

        errors = validate_event_envelope(data)

        assert any("metadata" in err and "dict" in err for err in errors)


class TestAtLeastOnceDelivery:
    """Test at-least-once delivery semantics (Phase 3, Point 8)."""

    def test_envelope_for_at_least_once_delivery(self):
        """Test preparing envelope for at-least-once delivery."""
        envelope = create_event_envelope(
            source="telegram", event_type="message.received", payload={"text": "hello"}, external_id="msg-1"
        )

        data = envelope_for_at_least_once_delivery(envelope)

        assert data["metadata"]["delivery_semantics"] == "at-least-once"
        assert data["metadata"]["requires_idempotent_consumer"] is True

    def test_at_least_once_preserves_envelope(self):
        """Test at-least-once delivery preserves original envelope data."""
        envelope = create_event_envelope(
            source="gcal", event_type="event.created", payload={"title": "Meeting"}, external_id="evt-1", seq=5
        )

        data = envelope_for_at_least_once_delivery(envelope)

        assert data["event_id"] == envelope.event_id
        assert data["event_ts"] == envelope.event_ts
        assert data["source"] == envelope.source
        assert data["type"] == envelope.type
        assert data["payload"] == envelope.payload
        assert data["seq"] == envelope.seq


class TestEventExtraction:
    """Test event extraction for processing."""

    def test_extract_event_for_processing(self):
        """Test extracting event type and payload."""
        envelope = create_event_envelope(
            source="cli",
            event_type="task.created",
            payload={"id": "task-001", "title": "New Task"},
            external_id="task-001",
        )

        event_type, payload = extract_event_for_processing(envelope)

        assert event_type == "task.created"
        assert payload == {"id": "task-001", "title": "New Task"}


class TestEventEnvelopeRequiredFields:
    """Test envelope has all required fields (Phase 3, Point 8)."""

    def test_envelope_has_event_id(self):
        """Test envelope has event_id."""
        envelope = create_event_envelope(
            source="telegram", event_type="message.received", payload={"text": "test"}, external_id="msg-1"
        )

        assert hasattr(envelope, "event_id")
        assert envelope.event_id is not None
        assert isinstance(envelope.event_id, str)

    def test_envelope_has_event_ts(self):
        """Test envelope has event_ts."""
        envelope = create_event_envelope(
            source="telegram", event_type="message.received", payload={"text": "test"}, external_id="msg-1"
        )

        assert hasattr(envelope, "event_ts")
        assert envelope.event_ts is not None
        assert isinstance(envelope.event_ts, str)
        # Should be ISO-8601 UTC
        assert "+00:00" in envelope.event_ts or envelope.event_ts.endswith("Z")

    def test_envelope_has_source(self):
        """Test envelope has source."""
        envelope = create_event_envelope(
            source="gcal", event_type="event.created", payload={"title": "Meeting"}, external_id="evt-1"
        )

        assert hasattr(envelope, "source")
        assert envelope.source == "gcal"

    def test_envelope_has_type(self):
        """Test envelope has type."""
        envelope = create_event_envelope(
            source="cli", event_type="task.updated", payload={"id": "task-001"}, external_id="task-001"
        )

        assert hasattr(envelope, "type")
        assert envelope.type == "task.updated"

    def test_envelope_has_payload(self):
        """Test envelope has payload."""
        payload = {"id": "note-001", "content": "Hello"}
        envelope = create_event_envelope(
            source="internal", event_type="note.created", payload=payload, external_id="note-001"
        )

        assert hasattr(envelope, "payload")
        assert envelope.payload == payload
        assert isinstance(envelope.payload, dict)

    def test_envelope_has_optional_seq(self):
        """Test envelope has optional seq field."""
        envelope = create_event_envelope(
            source="telegram", event_type="message.received", payload={"text": "test"}, external_id="msg-1", seq=42
        )

        assert hasattr(envelope, "seq")
        assert envelope.seq == 42


class TestDeterministicEventID:
    """Test event ID generation is deterministic."""

    def test_same_event_produces_same_id(self):
        """Test identical events produce identical event_id."""
        payload = {"message": "Hello", "user_id": 123}

        envelope1 = create_event_envelope(
            source="telegram", event_type="message.received", payload=payload.copy(), external_id="msg-456"
        )

        envelope2 = create_event_envelope(
            source="telegram", event_type="message.received", payload=payload.copy(), external_id="msg-456"
        )

        assert envelope1.event_id == envelope2.event_id

    def test_different_payloads_produce_different_ids(self):
        """Test different payloads produce different event_ids."""
        envelope1 = create_event_envelope(
            source="telegram", event_type="message.received", payload={"message": "Hello"}, external_id="msg-456"
        )

        envelope2 = create_event_envelope(
            source="telegram", event_type="message.received", payload={"message": "Goodbye"}, external_id="msg-456"
        )

        assert envelope1.event_id != envelope2.event_id

    def test_different_sources_produce_different_ids(self):
        """Test different sources produce different event_ids."""
        payload = {"message": "Hello"}

        envelope1 = create_event_envelope(
            source="telegram", event_type="message.received", payload=payload, external_id="msg-456"
        )

        envelope2 = create_event_envelope(
            source="cli", event_type="message.received", payload=payload, external_id="msg-456"
        )

        assert envelope1.event_id != envelope2.event_id
