"""Tests for ingress normalization & validation (Phase 2, Point 8)."""

import pytest

from kira.core.ingress import (
    IngressResult,
    IngressValidator,
    normalize_cli_payload,
    normalize_gcal_payload,
    normalize_telegram_payload,
    validate_shape,
    validate_types,
)


def test_ingress_result_boolean_conversion():
    """Test IngressResult boolean conversion."""
    valid_result = IngressResult(
        valid=True,
        normalized_payload={"key": "value"},
        errors=[],
        source="test",
    )
    assert bool(valid_result) is True
    
    invalid_result = IngressResult(
        valid=False,
        normalized_payload=None,
        errors=["error"],
        source="test",
    )
    assert bool(invalid_result) is False


def test_ingress_validator_initialization():
    """Test IngressValidator initialization."""
    validator = IngressValidator()
    assert validator.log_rejections is True
    assert validator._accepted_count == 0
    assert validator._rejected_count == 0


def test_validate_and_normalize_telegram():
    """Test validation and normalization of Telegram payload."""
    validator = IngressValidator()
    
    payload = {
        "message": {
            "message_id": 123,
            "text": "Hello",
            "date": 1633024800,
            "from": {
                "id": 456,
                "username": "alice",
                "first_name": "Alice",
            },
        },
    }
    
    result = validator.validate_and_normalize("telegram", payload)
    
    assert result.valid is True
    assert result.source == "telegram"
    assert result.normalized_payload["text"] == "Hello"
    assert result.normalized_payload["message_id"] == 123
    assert result.normalized_payload["user_id"] == 456


def test_validate_and_normalize_gcal():
    """Test validation and normalization of GCal payload."""
    validator = IngressValidator()
    
    payload = {
        "id": "event-123",
        "summary": "Team Meeting",
        "description": "Weekly sync",
        "start": {"dateTime": "2025-10-08T14:00:00Z"},
        "end": {"dateTime": "2025-10-08T15:00:00Z"},
        "location": "Room A",
        "attendees": [
            {"email": "alice@example.com"},
            {"email": "bob@example.com"},
        ],
    }
    
    result = validator.validate_and_normalize("gcal", payload)
    
    assert result.valid is True
    assert result.source == "gcal"
    assert result.normalized_payload["title"] == "Team Meeting"
    assert result.normalized_payload["start_time"] == "2025-10-08T14:00:00Z"
    assert len(result.normalized_payload["attendees"]) == 2


def test_validate_and_normalize_cli():
    """Test validation and normalization of CLI payload."""
    validator = IngressValidator()
    
    payload = {
        "command": "create-task",
        "args": ["Test Task"],
        "timestamp": "2025-10-08T12:00:00Z",
    }
    
    result = validator.validate_and_normalize("cli", payload)
    
    assert result.valid is True
    assert result.source == "cli"
    assert result.normalized_payload["source"] == "cli"
    assert result.normalized_payload["type"] == "cli.create-task"


def test_validate_and_normalize_rejects_invalid_type():
    """Test validation rejects non-dict payload."""
    validator = IngressValidator()
    
    result = validator.validate_and_normalize("test", "not a dict")
    
    assert result.valid is False
    assert len(result.errors) > 0
    assert "must be dict" in result.errors[0].lower()


def test_validate_and_normalize_generic_missing_type():
    """Test generic validation rejects payload without type."""
    validator = IngressValidator()
    
    payload = {"data": "value"}  # Missing 'type'
    
    result = validator.validate_and_normalize("custom", payload)
    
    assert result.valid is False
    assert any("type" in err.lower() for err in result.errors)


def test_validate_and_normalize_generic_valid():
    """Test generic validation accepts valid payload."""
    validator = IngressValidator()
    
    payload = {"type": "custom.event", "data": "value"}
    
    result = validator.validate_and_normalize("custom", payload)
    
    assert result.valid is True
    assert result.normalized_payload["type"] == "custom.event"
    assert result.normalized_payload["source"] == "custom"


def test_validator_tracks_acceptance_count():
    """Test validator tracks accepted payloads."""
    validator = IngressValidator()
    
    for i in range(3):
        payload = {"type": "test", "id": i}
        validator.validate_and_normalize("custom", payload)
    
    stats = validator.get_stats()
    assert stats["accepted"] == 3
    assert stats["rejected"] == 0


def test_validator_tracks_rejection_count():
    """Test validator tracks rejected payloads."""
    validator = IngressValidator()
    
    # Accept some
    validator.validate_and_normalize("custom", {"type": "test"})
    validator.validate_and_normalize("custom", {"type": "test"})
    
    # Reject some
    validator.validate_and_normalize("test", "not a dict")
    validator.validate_and_normalize("test", "also not a dict")
    
    stats = validator.get_stats()
    assert stats["accepted"] == 2
    assert stats["rejected"] == 2
    assert stats["total_processed"] == 4
    assert stats["rejection_rate"] == 0.5


def test_normalize_telegram_payload():
    """Test Telegram payload normalization."""
    payload = {
        "message": {
            "message_id": 123,
            "text": "Test message",
            "date": 1633024800,
            "from": {
                "id": 456,
                "username": "testuser",
                "first_name": "Test",
            },
        },
    }
    
    normalized = normalize_telegram_payload(payload)
    
    assert normalized["source"] == "telegram"
    assert normalized["type"] == "message"
    assert normalized["text"] == "Test message"
    assert normalized["message_id"] == 123
    assert normalized["user_id"] == 456
    assert normalized["username"] == "testuser"
    assert normalized["external_id"] == "tg-123"


def test_normalize_telegram_payload_missing_fields():
    """Test Telegram normalization handles missing fields."""
    payload = {}
    
    normalized = normalize_telegram_payload(payload)
    
    assert normalized["source"] == "telegram"
    assert normalized["type"] == "message"
    assert normalized["text"] == ""


def test_normalize_gcal_payload():
    """Test GCal payload normalization."""
    payload = {
        "id": "gcal-event-123",
        "summary": "Meeting",
        "description": "Important meeting",
        "location": "Office",
        "start": {"dateTime": "2025-10-08T10:00:00Z"},
        "end": {"dateTime": "2025-10-08T11:00:00Z"},
        "attendees": [
            {"email": "alice@example.com"},
            {"email": "bob@example.com"},
        ],
    }
    
    normalized = normalize_gcal_payload(payload)
    
    assert normalized["source"] == "gcal"
    assert normalized["type"] == "event"
    assert normalized["title"] == "Meeting"
    assert normalized["description"] == "Important meeting"
    assert normalized["location"] == "Office"
    assert normalized["start_time"] == "2025-10-08T10:00:00Z"
    assert normalized["end_time"] == "2025-10-08T11:00:00Z"
    assert normalized["attendees"] == ["alice@example.com", "bob@example.com"]
    assert normalized["external_id"] == "gcal-gcal-event-123"


def test_normalize_gcal_payload_all_day_event():
    """Test GCal normalization handles all-day events."""
    payload = {
        "id": "event-123",
        "summary": "Birthday",
        "start": {"date": "2025-10-08"},
        "end": {"date": "2025-10-09"},
    }
    
    normalized = normalize_gcal_payload(payload)
    
    assert normalized["start_time"] == "2025-10-08"
    assert normalized["end_time"] == "2025-10-09"


def test_normalize_cli_payload():
    """Test CLI payload normalization."""
    payload = {
        "command": "add",
        "args": ["task", "Test"],
        "timestamp": "2025-10-08T12:00:00Z",
    }
    
    normalized = normalize_cli_payload(payload)
    
    assert normalized["source"] == "cli"
    assert normalized["type"] == "cli.add"
    assert normalized["command"] == "add"
    assert normalized["external_id"] == "cli-2025-10-08T12:00:00Z"


def test_normalize_cli_payload_no_command():
    """Test CLI normalization handles missing command."""
    payload = {"data": "value"}
    
    normalized = normalize_cli_payload(payload)
    
    assert normalized["source"] == "cli"
    assert normalized["type"] == "cli.unknown"


def test_validate_shape_valid():
    """Test shape validation with valid payload."""
    payload = {"id": "123", "title": "Test", "status": "active"}
    required = ["id", "title", "status"]
    
    errors = validate_shape(payload, required)
    
    assert len(errors) == 0


def test_validate_shape_missing_fields():
    """Test shape validation catches missing fields."""
    payload = {"id": "123"}
    required = ["id", "title", "status"]
    
    errors = validate_shape(payload, required)
    
    assert len(errors) == 2
    assert any("title" in err for err in errors)
    assert any("status" in err for err in errors)


def test_validate_shape_null_fields():
    """Test shape validation catches null fields."""
    payload = {"id": "123", "title": None}
    required = ["id", "title"]
    
    errors = validate_shape(payload, required)
    
    assert len(errors) == 1
    assert "title" in errors[0]
    assert "null" in errors[0].lower()


def test_validate_types_valid():
    """Test type validation with valid types."""
    payload = {
        "id": "123",
        "count": 42,
        "active": True,
        "tags": ["a", "b"],
    }
    type_specs = {
        "id": str,
        "count": int,
        "active": bool,
        "tags": list,
    }
    
    errors = validate_types(payload, type_specs)
    
    assert len(errors) == 0


def test_validate_types_wrong_type():
    """Test type validation catches wrong types."""
    payload = {
        "id": 123,  # Should be str
        "count": "42",  # Should be int
    }
    type_specs = {
        "id": str,
        "count": int,
    }
    
    errors = validate_types(payload, type_specs)
    
    assert len(errors) == 2
    assert any("id" in err and "str" in err for err in errors)
    assert any("count" in err and "int" in err for err in errors)


def test_validate_types_ignores_none():
    """Test type validation ignores None values."""
    payload = {"id": None, "count": 42}
    type_specs = {"id": str, "count": int}
    
    errors = validate_types(payload, type_specs)
    
    # None is allowed
    assert len(errors) == 0


def test_validate_types_ignores_missing_fields():
    """Test type validation ignores missing fields."""
    payload = {"count": 42}
    type_specs = {"id": str, "count": int}
    
    errors = validate_types(payload, type_specs)
    
    # Missing fields are not type errors
    assert len(errors) == 0


def test_dod_invalid_ingress_never_reaches_consumers():
    """Test DoD: Invalid ingress never reaches consumers.
    
    Demonstrated by rejected payloads returning valid=False,
    which prevents publishing to event bus.
    """
    validator = IngressValidator()
    
    # Invalid payload
    result = validator.validate_and_normalize("test", "not a dict")
    
    # Should be rejected
    assert result.valid is False
    assert result.normalized_payload is None
    
    # In practice, adapter would check result.valid before publishing:
    if result.valid:
        # This code path would NOT be reached for invalid payload
        pytest.fail("Invalid payload should not reach this point")

