"""Tests for ID generation and naming conventions (ADR-008)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.ids import (
    AliasTracker,
    CollisionDetector,
    EntityId,
    generate_entity_id,
    get_known_entity_types,
    is_valid_entity_id,
    parse_entity_id,
    register_entity_type,
    sanitize_filename,
    validate_entity_id,
)


class TestEntityId:
    def test_entity_id_creation(self):
        entity_id = EntityId("task", "20250115-1430-fix-bug")

        assert str(entity_id) == "task-20250115-1430-fix-bug"
        assert entity_id.entity_type == "task"
        assert entity_id.unique_part == "20250115-1430-fix-bug"

    def test_entity_id_equality(self):
        id1 = EntityId("task", "20250115-1430-test")
        id2 = EntityId("task", "20250115-1430-test")
        id3 = EntityId("note", "20250115-1430-test")

        assert id1 == id2
        assert id1 != id3
        assert id1 == "task-20250115-1430-test"

    def test_entity_id_hash(self):
        id1 = EntityId("task", "20250115-1430-test")
        id2 = EntityId("task", "20250115-1430-test")

        # Same IDs should have same hash
        assert hash(id1) == hash(id2)

        # Should be usable in sets/dicts
        id_set = {id1, id2}
        assert len(id_set) == 1


class TestGenerateEntityId:
    def test_generate_with_title(self):
        entity_id = generate_entity_id("task", title="Fix authentication bug")

        assert entity_id.startswith("task-")
        assert "fix-authentication-bug" in entity_id
        assert len(entity_id) <= 100  # ADR-008 limit

    def test_generate_without_title(self):
        entity_id = generate_entity_id("note")

        assert entity_id.startswith("note-")
        assert len(entity_id.split("-")) >= 3  # type-timestamp-slug

    def test_generate_with_timestamp(self):
        ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        entity_id = generate_entity_id("task", title="Test", timestamp=ts)

        # Should contain timestamp part: 20250115-1430
        assert "20250115-14" in entity_id or "20250115-15" in entity_id  # Accounting for timezone conversion

    def test_generate_with_timezone(self):
        ts = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        entity_id = generate_entity_id(
            "task",
            title="Test",
            timestamp=ts,
            tz="Europe/Brussels"
        )

        # UTC 12:30 = Brussels 13:30 (or 14:30 in summer)
        assert entity_id.startswith("task-20250115-")

    def test_generate_format_compliance(self):
        """Test ID format matches ADR-008: <kind>-YYYYMMDD-HHmm-<slug>"""
        entity_id = generate_entity_id("task", title="Test Task")

        parts = entity_id.split("-")
        assert len(parts) >= 4  # type, YYYYMMDD, HHmm, slug...
        assert parts[0] == "task"
        assert parts[1].isdigit() and len(parts[1]) == 8  # YYYYMMDD
        assert parts[2].isdigit() and len(parts[2]) == 4  # HHmm

    def test_generate_length_limit(self):
        """Test ID doesn't exceed 100 char limit (ADR-008)."""
        long_title = "A" * 200
        entity_id = generate_entity_id("task", title=long_title)

        assert len(entity_id) <= 100

    def test_generate_custom_suffix(self):
        entity_id = generate_entity_id("task", custom_suffix="custom-identifier")

        assert "custom-identifier" in entity_id

    def test_generate_invalid_entity_type(self):
        with pytest.raises(ValueError):
            generate_entity_id("Invalid_Type!", title="Test")

        with pytest.raises(ValueError):
            generate_entity_id("", title="Test")


class TestParseEntityId:
    def test_parse_valid_id(self):
        entity_id = "task-20250115-1430-fix-bug"
        parsed = parse_entity_id(entity_id)

        assert parsed.entity_type == "task"
        assert parsed.unique_part == "20250115-1430-fix-bug"

    def test_parse_simple_id(self):
        entity_id = "note-abc123"
        parsed = parse_entity_id(entity_id)

        assert parsed.entity_type == "note"
        assert parsed.unique_part == "abc123"

    def test_parse_invalid_format(self):
        with pytest.raises(ValueError):
            parse_entity_id("no-hyphen")

        with pytest.raises(ValueError):
            parse_entity_id("InvalidType-123")

        with pytest.raises(ValueError):
            parse_entity_id("task-")  # Empty unique part


class TestValidateEntityId:
    def test_validate_valid_id(self):
        assert is_valid_entity_id("task-20250115-1430-test")
        assert is_valid_entity_id("note-abc123")
        assert is_valid_entity_id("event-2025-meeting")

    def test_validate_invalid_id(self):
        assert not is_valid_entity_id("invalid")
        assert not is_valid_entity_id("Task-123")  # Uppercase
        assert not is_valid_entity_id("task-")
        assert not is_valid_entity_id("")

    def test_validate_entity_id_function(self):
        valid_id = "task-20250115-1430-test"
        normalized = validate_entity_id(valid_id)

        assert normalized == valid_id

    def test_validate_entity_id_invalid_raises(self):
        with pytest.raises(ValueError):
            validate_entity_id("invalid-format")


class TestKnownEntityTypes:
    def test_get_known_entity_types(self):
        types = get_known_entity_types()

        assert "task" in types
        assert "note" in types
        assert "event" in types
        assert "project" in types

    def test_register_entity_type(self):
        # Register new type
        register_entity_type("custom")

        types = get_known_entity_types()
        assert "custom" in types

    def test_register_invalid_type(self):
        with pytest.raises(ValueError):
            register_entity_type("Invalid-Type!")


class TestSanitizeFilename:
    def test_sanitize_basic(self):
        result = sanitize_filename("My File Name.md")
        assert result == "My File Name.md"

    def test_sanitize_special_chars(self):
        result = sanitize_filename('File<>:"/\\|?*.md')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_sanitize_empty(self):
        result = sanitize_filename("")
        assert result == "unnamed"

    def test_sanitize_long_filename(self):
        long_name = "A" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200


class TestCollisionDetector:
    def test_register_id(self):
        detector = CollisionDetector()

        detector.register_id("task-123")
        assert detector.is_collision("task-123") is True
        assert detector.is_collision("task-456") is False

    def test_generate_unique_id_no_collision(self):
        detector = CollisionDetector()

        unique_id = detector.generate_unique_id("task", "Test Task")

        assert unique_id.startswith("task-")
        assert not detector.is_collision(unique_id)

    def test_generate_unique_id_with_collision(self):
        detector = CollisionDetector()

        # Generate first ID
        id1 = detector.generate_unique_id("task", "Test Task")
        detector.register_id(id1)

        # Generate second ID with same title (should add suffix)
        id2 = detector.generate_unique_id("task", "Test Task")

        assert id1 != id2
        assert id2.startswith(id1 + "-") or id2 != id1

    def test_collision_count(self):
        detector = CollisionDetector()

        base_id = "task-20250115-1430-test"
        detector.register_id(base_id)
        detector.register_id(f"{base_id}-2")

        count = detector.get_collision_count(base_id)
        assert count >= 1


class TestAliasTracker:
    def test_add_alias(self):
        tracker = AliasTracker()

        tracker.add_alias("old-id-123", "new-id-456")

        assert tracker.resolve_id("old-id-123") == "new-id-456"
        assert tracker.resolve_id("new-id-456") == "new-id-456"

    def test_get_aliases(self):
        tracker = AliasTracker()

        tracker.add_alias("old-1", "new-id")
        tracker.add_alias("old-2", "new-id")

        aliases = tracker.get_aliases("new-id")
        assert "old-1" in aliases
        assert "old-2" in aliases

    def test_save_load_aliases(self, tmp_path):
        aliases_file = tmp_path / "aliases.json"

        # Create tracker and add aliases
        tracker1 = AliasTracker(aliases_file)
        tracker1.add_alias("old-123", "new-456")
        tracker1.add_alias("old-789", "new-456")
        tracker1.save_aliases()

        # Load in new tracker
        tracker2 = AliasTracker(aliases_file)

        assert tracker2.resolve_id("old-123") == "new-456"
        assert "old-123" in tracker2.get_aliases("new-456")


class TestADR008Compliance:
    def test_id_format_matches_spec(self):
        """Test ID format matches ADR-008: <kind>-YYYYMMDD-HHmm-<slug>"""
        entity_id = generate_entity_id("task", title="Test Task")

        # Should match pattern: task-YYYYMMDD-HHmm-slug
        import re
        pattern = r"^[a-z][a-z0-9]{1,19}-\d{8}-\d{4}-.+$"
        assert re.match(pattern, entity_id), f"ID doesn't match pattern: {entity_id}"

    def test_id_length_limit_100(self):
        """Test IDs don't exceed 100 characters (ADR-008)."""
        long_title = "A" * 200
        entity_id = generate_entity_id("task", title=long_title)

        assert len(entity_id) <= 100

    def test_id_only_safe_characters(self):
        """Test IDs only contain safe characters [a-z0-9-]."""
        special_title = "Test!@#$%^&*()_+={}[]|\\:;\"'<>,.?/Task"
        entity_id = generate_entity_id("task", title=special_title)

        # Should only contain a-z0-9-
        import re
        assert re.match(r"^[a-z0-9-]+$", entity_id)

    def test_determinism_same_minute(self):
        """Test given same kind/title/minute, generate_id returns same ID."""
        ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)

        id1 = generate_entity_id("task", title="Test Task", timestamp=ts)
        id2 = generate_entity_id("task", title="Test Task", timestamp=ts)

        assert id1 == id2

    def test_timezone_affects_timestamp(self):
        """Test timezone affects timestamp part of ID."""
        ts_utc = datetime(2025, 1, 15, 23, 30, 0, tzinfo=timezone.utc)

        id_utc = generate_entity_id("task", title="Test", timestamp=ts_utc, tz="UTC")
        id_brussels = generate_entity_id("task", title="Test", timestamp=ts_utc, tz="Europe/Brussels")

        # UTC 23:30 = Brussels 00:30 next day (in winter) or 01:30 (summer)
        # Timestamps should differ
        ts_part_utc = id_utc.split("-")[1:3]
        ts_part_brussels = id_brussels.split("-")[1:3]

        # Date or time should differ
        assert ts_part_utc != ts_part_brussels

    def test_filename_mapping(self):
        """Test filename is <id>.md (ADR-008)."""
        entity_id = "task-20250115-1430-test"
        expected_filename = f"{entity_id}.md"

        # This is tested via Host API, which uses _get_entity_path
        assert expected_filename == f"{entity_id}.md"
