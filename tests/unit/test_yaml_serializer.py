"""Tests for deterministic YAML serialization (Phase 0, Point 2)."""

from datetime import UTC, datetime

import pytest

from kira.core.yaml_serializer import (
    get_canonical_key_order,
    normalize_timestamps_to_utc,
    parse_frontmatter,
    serialize_frontmatter,
    validate_strict_schema,
)


def test_canonical_key_order():
    """Test canonical key ordering."""
    keys = ["title", "id", "tags", "updated", "created", "custom_field", "another_field"]
    ordered = get_canonical_key_order(keys)

    # Known keys should come first in canonical order
    assert ordered.index("id") < ordered.index("title")
    assert ordered.index("title") < ordered.index("created")
    assert ordered.index("created") < ordered.index("updated")
    assert ordered.index("updated") < ordered.index("tags")

    # Unknown keys should come last, alphabetically
    assert ordered.index("tags") < ordered.index("another_field")
    assert ordered.index("another_field") < ordered.index("custom_field")


def test_normalize_timestamps_to_utc():
    """Test timestamp normalization to UTC."""
    # Test with datetime objects
    dt_naive = datetime(2025, 10, 8, 12, 30, 0)
    dt_utc = datetime(2025, 10, 8, 12, 30, 0, tzinfo=UTC)

    data = {
        "created": dt_naive,
        "updated": dt_utc,
        "title": "Test",
    }

    normalized = normalize_timestamps_to_utc(data)

    # Both should be ISO-8601 strings
    assert isinstance(normalized["created"], str)
    assert isinstance(normalized["updated"], str)

    # Both should be in UTC
    assert "+00:00" in normalized["created"] or "Z" in normalized["created"]
    assert "+00:00" in normalized["updated"] or "Z" in normalized["updated"]

    # Non-timestamp fields unchanged
    assert normalized["title"] == "Test"


def test_normalize_timestamps_string_format():
    """Test normalization of string timestamps."""
    data = {
        "created": "2025-10-08T12:30:00Z",
        "updated": "2025-10-08T14:30:00+02:00",  # CET -> UTC
    }

    normalized = normalize_timestamps_to_utc(data)

    # Both should be normalized to UTC ISO format
    assert isinstance(normalized["created"], str)
    assert isinstance(normalized["updated"], str)


def test_serialize_frontmatter_deterministic():
    """Test deterministic serialization."""
    data = {
        "tags": ["work", "urgent"],
        "title": "Test Task",
        "id": "task-123",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T13:00:00+00:00",
        "status": "todo",
    }

    # Serialize twice
    yaml1 = serialize_frontmatter(data)
    yaml2 = serialize_frontmatter(data)

    # Should be identical
    assert yaml1 == yaml2


def test_serialize_frontmatter_key_order():
    """Test that keys are ordered canonically."""
    data = {
        "updated": "2025-10-08T13:00:00+00:00",
        "tags": ["work"],
        "title": "Test",
        "id": "task-123",
        "created": "2025-10-08T12:00:00+00:00",
    }

    yaml_str = serialize_frontmatter(data)
    lines = yaml_str.split("\n")

    # Extract key order from YAML
    keys_in_yaml = []
    for line in lines:
        if ":" in line:
            key = line.split(":")[0].strip("- ")
            if key and not key.startswith("#"):
                keys_in_yaml.append(key)

    # Should be in canonical order: id, title, created, updated, tags
    assert keys_in_yaml[0] == "id"
    assert keys_in_yaml[1] == "title"
    # created and updated follow
    assert "created" in keys_in_yaml[2:4]
    assert "updated" in keys_in_yaml[2:4]


def test_parse_frontmatter_valid():
    """Test parsing valid YAML."""
    yaml_str = """
id: task-123
title: Test Task
created: 2025-10-08T12:00:00+00:00
updated: 2025-10-08T13:00:00+00:00
status: todo
tags:
  - work
  - urgent
"""

    data = parse_frontmatter(yaml_str)

    assert data["id"] == "task-123"
    assert data["title"] == "Test Task"
    assert data["status"] == "todo"
    assert data["tags"] == ["work", "urgent"]


def test_parse_frontmatter_empty():
    """Test parsing empty YAML."""
    data = parse_frontmatter("")
    assert data == {}


def test_parse_frontmatter_invalid():
    """Test parsing invalid YAML raises error."""
    invalid_yaml = "{ invalid yaml: [ "

    with pytest.raises(ValueError, match="Invalid YAML"):
        parse_frontmatter(invalid_yaml)


def test_round_trip_task():
    """Test round-trip serialization for Task entity."""
    original_data = {
        "id": "task-20251008-1230-test-task",
        "title": "Test Task",
        "status": "todo",
        "priority": "high",
        "created": "2025-10-08T12:30:00+00:00",
        "updated": "2025-10-08T12:30:00+00:00",
        "tags": ["work", "urgent"],
        "depends_on": ["task-456"],
    }

    # Serialize
    yaml_str = serialize_frontmatter(original_data)

    # Parse
    parsed_data = parse_frontmatter(yaml_str)

    # Serialize again
    yaml_str2 = serialize_frontmatter(parsed_data)

    # Should be identical
    assert yaml_str == yaml_str2

    # Data should match
    assert parsed_data["id"] == original_data["id"]
    assert parsed_data["title"] == original_data["title"]
    assert parsed_data["status"] == original_data["status"]
    assert parsed_data["tags"] == original_data["tags"]


def test_round_trip_note():
    """Test round-trip serialization for Note entity."""
    original_data = {
        "id": "note-20251008-1230-test-note",
        "title": "Test Note",
        "created": "2025-10-08T12:30:00+00:00",
        "updated": "2025-10-08T12:30:00+00:00",
        "tags": ["reference"],
        "category": "documentation",
    }

    # Round-trip
    yaml_str = serialize_frontmatter(original_data)
    parsed_data = parse_frontmatter(yaml_str)
    yaml_str2 = serialize_frontmatter(parsed_data)

    assert yaml_str == yaml_str2


def test_round_trip_event():
    """Test round-trip serialization for Event entity."""
    original_data = {
        "id": "event-20251008-1230-meeting",
        "title": "Team Meeting",
        "start_time": "2025-10-08T14:00:00+00:00",
        "end_time": "2025-10-08T15:00:00+00:00",
        "created": "2025-10-08T12:30:00+00:00",
        "updated": "2025-10-08T12:30:00+00:00",
        "location": "Conference Room A",
        "attendees": ["alice@example.com", "bob@example.com"],
    }

    # Round-trip
    yaml_str = serialize_frontmatter(original_data)
    parsed_data = parse_frontmatter(yaml_str)
    yaml_str2 = serialize_frontmatter(parsed_data)

    assert yaml_str == yaml_str2


def test_round_trip_with_xkira_metadata():
    """Test round-trip with x-kira sync metadata."""
    original_data = {
        "id": "event-123",
        "title": "Synced Event",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T13:00:00+00:00",
        "x-kira": {
            "source": "gcal",
            "version": 2,
            "remote_id": "gcal-event-abc123",
            "last_write_ts": "2025-10-08T13:00:00+00:00",
        },
    }

    # Round-trip
    yaml_str = serialize_frontmatter(original_data)
    parsed_data = parse_frontmatter(yaml_str)
    yaml_str2 = serialize_frontmatter(parsed_data)

    assert yaml_str == yaml_str2

    # Nested x-kira preserved
    assert parsed_data["x-kira"]["source"] == "gcal"
    assert parsed_data["x-kira"]["version"] == 2


def test_validate_strict_schema_task():
    """Test strict schema validation for Task."""
    # Valid task
    valid_task = {
        "id": "task-123",
        "title": "Test",
        "status": "todo",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    errors = validate_strict_schema("task", valid_task)
    assert len(errors) == 0


def test_validate_strict_schema_missing_required():
    """Test validation catches missing required fields."""
    incomplete_task = {
        "id": "task-123",
        "title": "Test",
        # Missing: status, created, updated, tags
    }

    errors = validate_strict_schema("task", incomplete_task)

    assert len(errors) > 0
    # Should report missing fields
    assert any("state" in err.lower() or "status" in err.lower() for err in errors)
    assert any("created" in err.lower() for err in errors)
    assert any("updated" in err.lower() for err in errors)
    # tags is optional, not required


def test_validate_strict_schema_tags_must_be_list():
    """Test validation ensures tags is a list."""
    invalid_task = {
        "id": "task-123",
        "title": "Test",
        "status": "todo",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": "not-a-list",  # Invalid
    }

    errors = validate_strict_schema("task", invalid_task)

    assert len(errors) > 0
    assert any("tags" in err.lower() and "list" in err.lower() for err in errors)


def test_validate_strict_schema_invalid_timestamp():
    """Test validation catches invalid timestamps."""
    invalid_task = {
        "id": "task-123",
        "title": "Test",
        "status": "todo",
        "created": "not-a-timestamp",  # Invalid
        "updated": "2025-10-08T12:00:00+00:00",
        "tags": [],
    }

    errors = validate_strict_schema("task", invalid_task)

    assert len(errors) > 0
    assert any("created" in err.lower() and "iso" in err.lower() for err in errors)


def test_deterministic_with_special_characters():
    """Test deterministic serialization with special characters."""
    data = {
        "id": "task-123",
        "title": "Test with 'quotes' and \"double quotes\"",
        "description": "Multi-line\ndescription\nwith special chars: &, *, @",
        "created": "2025-10-08T12:00:00+00:00",
        "updated": "2025-10-08T12:00:00+00:00",
        "status": "todo",
        "tags": ["special:char", "with/slash"],
    }

    # Round-trip
    yaml_str = serialize_frontmatter(data)
    parsed_data = parse_frontmatter(yaml_str)
    yaml_str2 = serialize_frontmatter(parsed_data)

    assert yaml_str == yaml_str2
    assert parsed_data["title"] == data["title"]
    assert parsed_data["description"] == data["description"]
