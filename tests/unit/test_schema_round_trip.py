"""Round-trip tests for YAML schema serialization (Phase 1, Point 3).

DoD: serialize→parse→equal for all entity types.
Tests deterministic serialization with key ordering, ISO-8601 UTC timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kira.core.yaml_serializer import (
    parse_frontmatter,
    serialize_frontmatter,
    normalize_timestamps_to_utc,
    get_canonical_key_order,
    validate_strict_schema,
)


class TestDeterministicSerialization:
    """Test deterministic YAML serialization."""
    
    def test_canonical_key_order(self):
        """Test keys are ordered according to CANONICAL_KEY_ORDER."""
        data = {
            "title": "Test Task",
            "id": "task-001",
            "tags": ["work"],
            "created": "2025-10-08T12:00:00+00:00",
            "status": "todo",
        }
        
        keys = list(data.keys())
        ordered_keys = get_canonical_key_order(keys)
        
        # Verify 'id' comes before 'title', then 'status', then 'created', then 'tags'
        assert ordered_keys.index("id") < ordered_keys.index("title")
        assert ordered_keys.index("title") < ordered_keys.index("status")
        assert ordered_keys.index("status") < ordered_keys.index("created")
        assert ordered_keys.index("created") < ordered_keys.index("tags")
    
    def test_unknown_keys_alphabetically(self):
        """Test unknown keys are sorted alphabetically after known keys."""
        data = {
            "zebra": "z",
            "id": "1",
            "alpha": "a",
            "title": "Test",
        }
        
        keys = list(data.keys())
        ordered_keys = get_canonical_key_order(keys)
        
        # Known keys first (id, title)
        assert ordered_keys[0] == "id"
        assert ordered_keys[1] == "title"
        
        # Unknown keys alphabetically
        assert ordered_keys[2] == "alpha"
        assert ordered_keys[3] == "zebra"


class TestTimestampNormalization:
    """Test timestamp normalization to UTC."""
    
    def test_datetime_to_utc_iso8601(self):
        """Test datetime objects are converted to ISO-8601 UTC."""
        dt = datetime(2025, 10, 8, 12, 30, 0, tzinfo=timezone.utc)
        data = {"created": dt}
        
        normalized = normalize_timestamps_to_utc(data)
        
        assert isinstance(normalized["created"], str)
        assert normalized["created"] == "2025-10-08T12:30:00+00:00"
    
    def test_naive_datetime_assumes_utc(self):
        """Test naive datetime is assumed to be UTC."""
        dt = datetime(2025, 10, 8, 12, 30, 0)  # No timezone
        data = {"created": dt}
        
        normalized = normalize_timestamps_to_utc(data)
        
        assert "+00:00" in normalized["created"]
    
    def test_local_datetime_converted_to_utc(self):
        """Test local datetime is converted to UTC."""
        from zoneinfo import ZoneInfo
        
        # 14:30 Brussels (UTC+2) = 12:30 UTC
        dt = datetime(2025, 10, 8, 14, 30, 0, tzinfo=ZoneInfo("Europe/Brussels"))
        data = {"created": dt}
        
        normalized = normalize_timestamps_to_utc(data)
        
        assert "12:30:00" in normalized["created"]
        assert "+00:00" in normalized["created"]
    
    def test_nested_timestamps_normalized(self):
        """Test timestamps in nested dicts are normalized."""
        data = {
            "created": "2025-10-08T12:00:00Z",
            "x-kira": {
                "last_write_ts": datetime(2025, 10, 8, 14, 0, 0, tzinfo=timezone.utc)
            }
        }
        
        normalized = normalize_timestamps_to_utc(data)
        
        assert isinstance(normalized["x-kira"]["last_write_ts"], str)
        assert "+00:00" in normalized["x-kira"]["last_write_ts"]


class TestRoundTripTask:
    """Test round-trip serialization for Task entities."""
    
    def test_task_basic_round_trip(self):
        """Test basic task serializes and parses back identical."""
        original = {
            "id": "task-20251008-1200",
            "title": "Implement Phase 1",
            "status": "doing",
            "created": "2025-10-08T10:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": ["development", "phase1"],
        }
        
        # Serialize
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        
        # Parse
        parsed = parse_frontmatter(yaml_str)
        
        # Compare
        assert parsed == original
    
    def test_task_with_all_fields(self):
        """Test task with all optional fields."""
        original = {
            "id": "task-20251008-1200",
            "title": "Complex Task",
            "status": "doing",
            "priority": "high",
            "created": "2025-10-08T10:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "due_date": "2025-10-15T18:00:00+00:00",
            "start_ts": "2025-10-08T12:00:00+00:00",
            "tags": ["urgent", "blocked"],
            "assignee": "Alice",
            "estimate": "4h",
            "links": ["[[note-001]]", "[[task-002]]"],
            "depends_on": ["task-002"],
            "x-kira": {
                "source": "telegram",
                "version": 3,
                "last_write_ts": "2025-10-08T12:00:00+00:00",
            }
        }
        
        # Serialize
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        
        # Parse
        parsed = parse_frontmatter(yaml_str)
        
        # Compare
        assert parsed == original
    
    def test_task_double_round_trip(self):
        """Test serialize→parse→serialize yields identical YAML."""
        original = {
            "id": "task-001",
            "title": "Test Task",
            "status": "todo",
            "created": "2025-10-08T10:00:00+00:00",
            "updated": "2025-10-08T10:00:00+00:00",
            "tags": ["test"],
        }
        
        # First round
        yaml1 = serialize_frontmatter(original, normalize_timestamps=False)
        parsed1 = parse_frontmatter(yaml1)
        
        # Second round
        yaml2 = serialize_frontmatter(parsed1, normalize_timestamps=False)
        parsed2 = parse_frontmatter(yaml2)
        
        # YAML strings should be identical
        assert yaml1 == yaml2
        # Parsed data should be identical
        assert parsed1 == parsed2


class TestRoundTripNote:
    """Test round-trip serialization for Note entities."""
    
    def test_note_basic_round_trip(self):
        """Test basic note serializes and parses back identical."""
        original = {
            "id": "note-20251008-1200",
            "title": "Meeting Notes",
            "state": "active",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": ["meeting", "q4-planning"],
        }
        
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        parsed = parse_frontmatter(yaml_str)
        
        assert parsed == original
    
    def test_note_with_links(self):
        """Test note with backlinks."""
        original = {
            "id": "note-001",
            "title": "Architecture Decision",
            "state": "active",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": ["architecture"],
            "links": ["[[task-001]]", "[[note-002]]"],
            "relates_to": ["adr-001"],
        }
        
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        parsed = parse_frontmatter(yaml_str)
        
        assert parsed == original


class TestRoundTripEvent:
    """Test round-trip serialization for Event entities."""
    
    def test_event_basic_round_trip(self):
        """Test basic event serializes and parses back identical."""
        original = {
            "id": "event-20251008-1400",
            "title": "Team Standup",
            "state": "scheduled",
            "created": "2025-10-08T10:00:00+00:00",
            "updated": "2025-10-08T10:00:00+00:00",
            "start_time": "2025-10-08T14:00:00+00:00",
            "end_time": "2025-10-08T14:30:00+00:00",
            "tags": ["meeting"],
        }
        
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        parsed = parse_frontmatter(yaml_str)
        
        assert parsed == original
    
    def test_event_with_attendees(self):
        """Test event with attendees and location."""
        original = {
            "id": "event-001",
            "title": "Sprint Planning",
            "state": "scheduled",
            "created": "2025-10-08T10:00:00+00:00",
            "updated": "2025-10-08T10:00:00+00:00",
            "start_time": "2025-10-09T09:00:00+00:00",
            "end_time": "2025-10-09T11:00:00+00:00",
            "location": "Conference Room A",
            "attendees": ["Alice", "Bob", "Charlie"],
            "calendar": "work",
            "tags": ["planning"],
            "x-kira": {
                "source": "gcal",
                "remote_id": "abc123xyz",
                "version": 1,
            }
        }
        
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        parsed = parse_frontmatter(yaml_str)
        
        assert parsed == original


class TestStrictSchemaValidation:
    """Test strict schema validation (Phase 1, Point 3)."""
    
    def test_task_valid_schema(self):
        """Test valid task passes schema validation."""
        data = {
            "id": "task-001",
            "title": "Test Task",
            "status": "todo",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": ["test"],
        }
        
        errors = validate_strict_schema("task", data)
        assert errors == []
    
    def test_task_missing_required_field(self):
        """Test task missing required field fails validation."""
        data = {
            "id": "task-001",
            "title": "Test Task",
            # Missing: status, created, updated, tags
        }
        
        errors = validate_strict_schema("task", data)
        
        # Should have errors for missing fields
        assert len(errors) > 0
        assert any("state" in err.lower() or "status" in err.lower() for err in errors)
    
    def test_task_invalid_timestamp(self):
        """Test task with invalid timestamp fails validation."""
        data = {
            "id": "task-001",
            "title": "Test Task",
            "status": "todo",
            "created": "not-a-timestamp",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": [],
        }
        
        errors = validate_strict_schema("task", data)
        
        # Should have error for invalid timestamp
        assert len(errors) > 0
        assert any("created" in err for err in errors)
    
    def test_task_tags_not_list(self):
        """Test task with non-list tags fails validation."""
        data = {
            "id": "task-001",
            "title": "Test Task",
            "status": "todo",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": "not-a-list",  # Should be list
        }
        
        errors = validate_strict_schema("task", data)
        
        # Should have error for tags type
        assert len(errors) > 0
        assert any("tags" in err for err in errors)


class TestSpecialCharactersRoundTrip:
    """Test round-trip with special characters."""
    
    def test_title_with_colon(self):
        """Test title with colon serializes correctly."""
        original = {
            "id": "task-001",
            "title": "Phase 1: Canonical Schema",
            "status": "doing",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": [],
        }
        
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        parsed = parse_frontmatter(yaml_str)
        
        assert parsed == original
        assert parsed["title"] == original["title"]
    
    def test_tags_with_special_chars(self):
        """Test tags with special characters."""
        original = {
            "id": "task-001",
            "title": "Test",
            "status": "todo",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": ["bug-fix", "high-priority", "v0.1.0"],
        }
        
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        parsed = parse_frontmatter(yaml_str)
        
        assert parsed == original
    
    def test_empty_lists(self):
        """Test empty lists serialize correctly."""
        original = {
            "id": "task-001",
            "title": "Test",
            "status": "todo",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": [],
            "links": [],
        }
        
        yaml_str = serialize_frontmatter(original, normalize_timestamps=False)
        parsed = parse_frontmatter(yaml_str)
        
        assert parsed == original


class TestConsistentOutput:
    """Test serialization produces consistent output."""
    
    def test_same_input_same_output(self):
        """Test same data always produces same YAML."""
        data = {
            "id": "task-001",
            "title": "Test",
            "status": "todo",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": ["a", "b", "c"],
        }
        
        yaml1 = serialize_frontmatter(data, normalize_timestamps=False)
        yaml2 = serialize_frontmatter(data, normalize_timestamps=False)
        yaml3 = serialize_frontmatter(data, normalize_timestamps=False)
        
        assert yaml1 == yaml2 == yaml3
    
    def test_key_order_independent_of_input_order(self):
        """Test key order in output is independent of input order."""
        # Same data, different input order
        data1 = {
            "tags": [],
            "title": "Test",
            "id": "task-001",
            "updated": "2025-10-08T12:00:00+00:00",
            "status": "todo",
            "created": "2025-10-08T12:00:00+00:00",
        }
        
        data2 = {
            "id": "task-001",
            "title": "Test",
            "status": "todo",
            "created": "2025-10-08T12:00:00+00:00",
            "updated": "2025-10-08T12:00:00+00:00",
            "tags": [],
        }
        
        yaml1 = serialize_frontmatter(data1, normalize_timestamps=False)
        yaml2 = serialize_frontmatter(data2, normalize_timestamps=False)
        
        # Output should be identical despite different input order
        assert yaml1 == yaml2

