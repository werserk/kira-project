"""Tests for domain validation (Phase 1, Point 5)."""

import pytest

from kira.core.validation import (
    ValidationError,
    ValidationResult,
    validate_entity,
    validate_task_specific,
    validate_note_specific,
    validate_event_specific,
)


def test_validation_result_boolean_conversion():
    """Test ValidationResult boolean conversion."""
    valid = ValidationResult(valid=True)
    assert bool(valid) is True

    invalid = ValidationResult(valid=False, errors=["error 1"])
    assert bool(invalid) is False


def test_validation_result_string_representation():
    """Test ValidationResult string representation."""
    valid = ValidationResult(valid=True)
    assert str(valid) == "Valid"

    invalid = ValidationResult(valid=False, errors=["error 1", "error 2"])
    assert "Invalid" in str(invalid)
    assert "error 1" in str(invalid)


def test_validate_task_valid():
    """Test validation of valid task."""
    task_data = {
        "id": "task-123",
        "title": "Test Task",
        "status": "todo",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": ["work"],
    }

    result = validate_entity("task", task_data)
    assert result.valid is True
    assert len(result.errors) == 0


def test_validate_task_invalid_status():
    """Test task validation catches invalid status."""
    task_data = {
        "id": "task-123",
        "title": "Test Task",
        "status": "invalid-status",  # Invalid
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    errors = validate_task_specific(task_data)
    assert len(errors) > 0
    assert any("Invalid status" in err for err in errors)


def test_validate_task_blocked_requires_reason():
    """Test blocked tasks require blocked_reason."""
    task_data = {
        "id": "task-123",
        "title": "Test Task",
        "status": "blocked",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    errors = validate_task_specific(task_data)
    assert len(errors) > 0
    assert any("blocked_reason" in err.lower() for err in errors)


def test_validate_task_done_requires_done_ts():
    """Test done tasks require done_ts."""
    task_data = {
        "id": "task-123",
        "title": "Test Task",
        "status": "done",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    errors = validate_task_specific(task_data)
    assert len(errors) > 0
    assert any("done_ts" in err.lower() for err in errors)


def test_validate_task_invalid_priority():
    """Test task validation catches invalid priority."""
    task_data = {
        "id": "task-123",
        "title": "Test Task",
        "status": "todo",
        "priority": "critical",  # Invalid
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    errors = validate_task_specific(task_data)
    assert len(errors) > 0
    assert any("Invalid priority" in err for err in errors)


def test_validate_task_invalid_estimate_format():
    """Test task validation catches invalid estimate format."""
    task_data = {
        "id": "task-123",
        "title": "Test Task",
        "status": "todo",
        "estimate": "two hours",  # Invalid format
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    errors = validate_task_specific(task_data)
    assert len(errors) > 0
    assert any("estimate" in err.lower() for err in errors)


def test_validate_task_valid_estimate_formats():
    """Test valid estimate formats are accepted."""
    valid_estimates = ["2h", "30m", "1d", "1.5h", "0.5d"]

    for estimate in valid_estimates:
        task_data = {
            "id": "task-123",
            "title": "Test Task",
            "status": "todo",
            "estimate": estimate,
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": [],
        }

        errors = validate_task_specific(task_data)
        # Should not have estimate format errors
        assert not any("estimate format" in err.lower() for err in errors)


def test_validate_note_valid():
    """Test validation of valid note."""
    note_data = {
        "id": "note-123",
        "title": "Test Note",
        "category": "reference",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],  # Required by schema
    }

    result = validate_entity("note", note_data)
    # May have warnings but note-specific validation should pass
    note_errors = validate_note_specific(note_data)
    assert len(note_errors) == 0  # Has category, so should be valid


def test_validate_note_should_have_category_or_tags():
    """Test notes should have category or tags for organization."""
    note_data = {
        "id": "note-123",
        "title": "Test Note",
        # No category or tags
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
    }

    errors = validate_note_specific(note_data)
    assert len(errors) > 0
    assert any("category" in err.lower() or "tags" in err.lower() for err in errors)


def test_validate_event_valid():
    """Test validation of valid event."""
    event_data = {
        "id": "event-123",
        "title": "Test Event",
        "start_time": "2025-10-08T14:00:00+00:00",
        "end_time": "2025-10-08T15:00:00+00:00",
    }

    result = validate_entity("event", event_data)
    # May have schema errors for missing created/updated, but event-specific should be valid
    event_errors = validate_event_specific(event_data)
    assert len(event_errors) == 0


def test_validate_event_requires_start_time():
    """Test events require start_time."""
    event_data = {
        "id": "event-123",
        "title": "Test Event",
        # Missing start_time
    }

    errors = validate_event_specific(event_data)
    assert len(errors) > 0
    assert any("start_time" in err.lower() for err in errors)


def test_validate_event_end_time_after_start_time():
    """Test event end_time must be after start_time."""
    event_data = {
        "id": "event-123",
        "title": "Test Event",
        "start_time": "2025-10-08T15:00:00+00:00",
        "end_time": "2025-10-08T14:00:00+00:00",  # Before start_time
    }

    errors = validate_event_specific(event_data)
    assert len(errors) > 0
    assert any("after start_time" in err.lower() for err in errors)


def test_validate_common_rules_empty_title():
    """Test validation catches empty title."""
    task_data = {
        "id": "task-123",
        "title": "   ",  # Empty after strip
        "status": "todo",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    result = validate_entity("task", task_data)
    assert not result.valid
    assert any("empty" in err.lower() for err in result.errors)


def test_validate_common_rules_title_too_long():
    """Test validation catches title that's too long."""
    task_data = {
        "id": "task-123",
        "title": "A" * 250,  # Too long (max 200)
        "status": "todo",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    result = validate_entity("task", task_data)
    assert not result.valid
    assert any("too long" in err.lower() for err in result.errors)


def test_validate_common_rules_links_must_be_list():
    """Test validation catches non-list link fields."""
    task_data = {
        "id": "task-123",
        "title": "Test Task",
        "status": "todo",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
        "relates_to": "task-456",  # Should be a list
    }

    result = validate_entity("task", task_data)
    assert not result.valid
    assert any("must be a list" in err.lower() for err in result.errors)


def test_validate_common_rules_invalid_entity_id_in_links():
    """Test validation catches invalid entity IDs in links."""
    task_data = {
        "id": "task-123",
        "title": "Test Task",
        "status": "todo",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
        "depends_on": ["task-456", "INVALID_ID"],  # Second ID is invalid format
    }

    result = validate_entity("task", task_data)
    assert not result.valid
    assert any("invalid entity id" in err.lower() for err in result.errors)


def test_validation_error_exception():
    """Test ValidationError exception."""
    errors = ["Error 1", "Error 2"]

    try:
        raise ValidationError("Validation failed", errors=errors)
    except ValidationError as exc:
        assert str(exc) == "Validation failed"
        assert exc.errors == errors


def test_validation_collects_multiple_errors():
    """Test validation collects all errors, not just first."""
    task_data = {
        "id": "task-123",
        "title": "",  # Empty
        "status": "invalid",  # Invalid status
        "priority": "super-urgent",  # Invalid priority
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    result = validate_entity("task", task_data)
    assert not result.valid
    # Should have multiple errors
    assert len(result.errors) >= 3


def test_validate_entity_with_missing_required_fields():
    """Test validation catches missing required fields (from schema)."""
    task_data = {
        "id": "task-123",
        # Missing: title, status, created, updated, tags
    }

    result = validate_entity("task", task_data)
    assert not result.valid
    assert len(result.errors) > 0


def test_invalid_entities_never_touch_disk():
    """Test DoD: Invalid entities never touch disk.

    This is tested indirectly - validation happens before
    any disk operations in Host API.
    """
    # This test documents the requirement
    # Actual enforcement is in Host API integration tests
    pass
