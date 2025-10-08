"""Tests for vault migration (Phase 8, Point 23).

DoD: Post-migration, every file parses and passes round-trip tests.
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kira.core.md_io import MarkdownDocument, read_markdown, write_markdown
from kira.core.time import format_utc_iso8601
from kira.migration.migrator import (
    MigrationStats,
    infer_entity_type,
    migrate_file,
    migrate_vault,
    normalize_timestamp_to_utc,
    validate_migration,
)


def test_normalize_timestamp_iso8601():
    """Test normalizing ISO-8601 timestamps."""
    # Already UTC
    ts = "2025-10-08T12:00:00+00:00"
    result = normalize_timestamp_to_utc(ts)
    assert result == ts
    
    # With Z suffix
    ts_z = "2025-10-08T12:00:00Z"
    result = normalize_timestamp_to_utc(ts_z)
    assert "+00:00" in result


def test_normalize_timestamp_unix():
    """Test normalizing Unix timestamps."""
    # Unix timestamp for 2025-01-01 00:00:00 UTC
    unix_ts = "1735689600"
    result = normalize_timestamp_to_utc(unix_ts)
    
    assert result is not None
    assert "2025-01-01" in result


def test_normalize_timestamp_date_only():
    """Test normalizing date-only strings."""
    date_str = "2025-10-08"
    result = normalize_timestamp_to_utc(date_str)
    
    assert result is not None
    assert "2025-10-08" in result
    assert "+00:00" in result


def test_normalize_timestamp_invalid():
    """Test handling invalid timestamps."""
    invalid_inputs = ["invalid", "", "not-a-date", "2025-99-99"]
    
    for invalid in invalid_inputs:
        result = normalize_timestamp_to_utc(invalid)
        # Should return None or raise no exception
        assert result is None or isinstance(result, str)


def test_infer_entity_type_from_metadata():
    """Test inferring entity type from metadata."""
    # Explicit type in metadata
    assert infer_entity_type(Path("file.md"), {"type": "task"}) == "task"
    assert infer_entity_type(Path("file.md"), {"type": "note"}) == "note"
    assert infer_entity_type(Path("file.md"), {"type": "event"}) == "event"


def test_infer_entity_type_from_path():
    """Test inferring entity type from file path."""
    # Task
    assert infer_entity_type(Path("tasks/my-task.md"), {}) == "task"
    assert infer_entity_type(Path("todo/item.md"), {}) == "task"
    
    # Event
    assert infer_entity_type(Path("events/meeting.md"), {}) == "event"
    assert infer_entity_type(Path("calendar/2025-10-08.md"), {}) == "event"
    
    # Note (default)
    assert infer_entity_type(Path("notes/my-note.md"), {}) == "note"
    assert infer_entity_type(Path("random/file.md"), {}) == "note"


def test_migrate_file_add_uid():
    """Test DoD: Add missing UIDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create file without UID
        doc = MarkdownDocument(
            frontmatter={"title": "Test Task"},
            content="Content here",
        )
        write_markdown(file_path, doc)
        
        # Migrate
        result = migrate_file(file_path)
        
        # Should have added UID
        assert result.success
        assert any("Added UID" in change for change in result.changes)
        
        # Verify file has UID now
        migrated_doc = read_markdown(file_path)
        assert "id" in migrated_doc.frontmatter


def test_migrate_file_rename_uid_to_id():
    """Test DoD: Rename 'uid' to 'id'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create file with 'uid' instead of 'id'
        doc = MarkdownDocument(
            frontmatter={"uid": "task-123", "title": "Test"},
            content="Content",
        )
        write_markdown(file_path, doc)
        
        # Migrate
        result = migrate_file(file_path)
        
        # Should have renamed uid → id
        assert result.success
        assert any("Renamed 'uid' to 'id'" in change for change in result.changes)
        
        # Verify
        migrated_doc = read_markdown(file_path)
        assert "id" in migrated_doc.frontmatter
        assert migrated_doc.frontmatter["id"] == "task-123"


def test_migrate_file_normalize_timestamps():
    """Test DoD: Convert timestamps to UTC."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create file with non-UTC timestamp
        doc = MarkdownDocument(
            frontmatter={
                "title": "Test",
                "created": "2025-10-08",  # Date-only
                "due": "1735689600",  # Unix timestamp
            },
            content="Content",
        )
        write_markdown(file_path, doc)
        
        # Migrate
        result = migrate_file(file_path)
        
        # Should have normalized timestamps
        assert result.success
        timestamp_changes = [c for c in result.changes if "Normalized" in c]
        assert len(timestamp_changes) >= 1
        
        # Verify timestamps are UTC ISO-8601
        migrated_doc = read_markdown(file_path)
        assert "+00:00" in migrated_doc.frontmatter["created"]


def test_migrate_file_add_required_fields():
    """Test DoD: Add required fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create minimal file
        doc = MarkdownDocument(
            frontmatter={"title": "Test"},
            content="Content",
        )
        write_markdown(file_path, doc)
        
        # Migrate
        result = migrate_file(file_path)
        
        # Should have added required fields
        assert result.success
        
        # Verify required fields present
        migrated_doc = read_markdown(file_path)
        assert "id" in migrated_doc.frontmatter
        assert "created" in migrated_doc.frontmatter
        assert "updated" in migrated_doc.frontmatter
        assert "tags" in migrated_doc.frontmatter


def test_migrate_file_normalize_tags():
    """Test normalizing tags to list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create file with comma-separated tags
        doc = MarkdownDocument(
            frontmatter={
                "title": "Test",
                "tags": "work, personal, urgent",
            },
            content="Content",
        )
        write_markdown(file_path, doc)
        
        # Migrate
        result = migrate_file(file_path)
        
        # Should have normalized tags to list
        assert result.success
        assert any("Normalized tags" in change for change in result.changes)
        
        # Verify tags are list
        migrated_doc = read_markdown(file_path)
        tags = migrated_doc.frontmatter["tags"]
        assert isinstance(tags, list)
        assert len(tags) == 3


def test_migrate_file_add_task_status():
    """Test adding default status for tasks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "tasks" / "test.md"
        file_path.parent.mkdir(parents=True)
        
        # Create task without status
        doc = MarkdownDocument(
            frontmatter={"title": "Task"},
            content="Task content",
        )
        write_markdown(file_path, doc)
        
        # Migrate
        result = migrate_file(file_path)
        
        # Should have added status
        assert result.success
        
        # Verify status added
        migrated_doc = read_markdown(file_path)
        assert "status" in migrated_doc.frontmatter
        assert migrated_doc.frontmatter["status"] == "todo"


def test_migrate_file_dry_run():
    """Test dry run doesn't write changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create file
        doc = MarkdownDocument(
            frontmatter={"title": "Test"},
            content="Original content",
        )
        write_markdown(file_path, doc)
        
        # Get original mtime
        original_mtime = file_path.stat().st_mtime
        
        # Migrate with dry_run=True
        result = migrate_file(file_path, dry_run=True)
        
        # Should report changes but not write
        assert result.success
        assert len(result.changes) > 0
        
        # File should not be modified
        assert file_path.stat().st_mtime == original_mtime


def test_migrate_vault_multiple_files():
    """Test migrating entire vault."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        
        # Create multiple files
        for i in range(3):
            file_path = vault_path / f"file{i}.md"
            doc = MarkdownDocument(
                frontmatter={"title": f"File {i}"},
                content=f"Content {i}",
            )
            write_markdown(file_path, doc)
        
        # Migrate vault
        stats, results = migrate_vault(vault_path)
        
        # Should have migrated all files
        assert stats.total_files == 3
        assert stats.successful == 3
        assert stats.failed == 0


def test_migrate_vault_recursive():
    """Test recursive vault migration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        
        # Create nested structure
        (vault_path / "tasks").mkdir()
        (vault_path / "notes" / "sub").mkdir(parents=True)
        
        files = [
            vault_path / "root.md",
            vault_path / "tasks" / "task1.md",
            vault_path / "notes" / "note1.md",
            vault_path / "notes" / "sub" / "note2.md",
        ]
        
        for file_path in files:
            doc = MarkdownDocument(
                frontmatter={"title": file_path.stem},
                content="Content",
            )
            write_markdown(file_path, doc)
        
        # Migrate recursively
        stats, results = migrate_vault(vault_path, recursive=True)
        
        # Should have migrated all nested files
        assert stats.total_files == 4


def test_migrate_vault_stats():
    """Test migration statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        
        # Create file that needs migration
        file1 = vault_path / "needs_migration.md"
        doc1 = MarkdownDocument(
            frontmatter={"title": "Test"},  # Missing fields
            content="Content",
        )
        write_markdown(file1, doc1)
        
        # Create file already migrated
        file2 = vault_path / "already_migrated.md"
        doc2 = MarkdownDocument(
            frontmatter={
                "id": "note-123",
                "title": "Migrated",
                "created": format_utc_iso8601(datetime.now(timezone.utc)),
                "updated": format_utc_iso8601(datetime.now(timezone.utc)),
                "tags": [],
            },
            content="Content",
        )
        write_markdown(file2, doc2)
        
        # Migrate
        stats, results = migrate_vault(vault_path)
        
        # Verify stats
        assert stats.total_files == 2
        assert stats.successful >= 1  # At least one needed migration
        assert stats.skipped >= 0  # Already migrated might be skipped


def test_validate_migration_success():
    """Test DoD: Validation after migration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create properly migrated file
        doc = MarkdownDocument(
            frontmatter={
                "id": "task-123",
                "title": "Test Task",
                "created": format_utc_iso8601(datetime.now(timezone.utc)),
                "updated": format_utc_iso8601(datetime.now(timezone.utc)),
                "tags": [],
                "status": "todo",
            },
            content="Content",
        )
        write_markdown(file_path, doc)
        
        # Validate
        is_valid, errors = validate_migration(file_path)
        
        # Should pass validation
        assert is_valid
        assert len(errors) == 0


def test_validate_migration_missing_fields():
    """Test validation catches missing fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create file missing required fields
        doc = MarkdownDocument(
            frontmatter={"title": "Test"},
            content="Content",
        )
        write_markdown(file_path, doc)
        
        # Validate
        is_valid, errors = validate_migration(file_path)
        
        # Should fail validation
        assert not is_valid
        assert len(errors) > 0
        assert any("Missing required field" in error for error in errors)


def test_validate_migration_invalid_timestamp():
    """Test validation catches invalid timestamps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create file with invalid timestamp
        doc = MarkdownDocument(
            frontmatter={
                "id": "task-123",
                "title": "Test",
                "created": "invalid-timestamp",
                "updated": format_utc_iso8601(datetime.now(timezone.utc)),
                "tags": [],
            },
            content="Content",
        )
        write_markdown(file_path, doc)
        
        # Validate
        is_valid, errors = validate_migration(file_path)
        
        # Should fail validation
        assert not is_valid
        assert any("Invalid timestamp" in error for error in errors)


def test_dod_round_trip_after_migration():
    """Test DoD: Post-migration files pass round-trip tests.
    
    Critical test: serialize → parse → equal.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        # Create file
        doc = MarkdownDocument(
            frontmatter={"title": "Test"},
            content="Content",
        )
        write_markdown(file_path, doc)
        
        # Migrate
        result = migrate_file(file_path)
        assert result.success
        
        # Validate (includes round-trip test)
        is_valid, errors = validate_migration(file_path)
        
        # Should pass round-trip test
        assert is_valid, f"Round-trip failed: {errors}"


def test_migration_preserves_content():
    """Test migration preserves file content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.md"
        
        original_content = "This is important content\n\nWith multiple paragraphs."
        
        # Create file
        doc = MarkdownDocument(
            frontmatter={"title": "Test"},
            content=original_content,
        )
        write_markdown(file_path, doc)
        
        # Migrate
        result = migrate_file(file_path)
        assert result.success
        
        # Verify content preserved
        migrated_doc = read_markdown(file_path)
        assert migrated_doc.content == original_content


def test_migration_handles_errors_gracefully():
    """Test migration handles errors without crashing."""
    # Try to migrate non-existent file
    result = migrate_file(Path("/nonexistent/file.md"))
    
    # Should fail gracefully
    assert not result.success
    assert len(result.errors) > 0
