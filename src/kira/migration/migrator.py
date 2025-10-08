"""Vault file migration to new schema (Phase 8, Point 23).

Migrates existing .md files to:
- New front-matter schema
- Add missing UIDs
- Convert timestamps to UTC
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..core.ids import generate_entity_id
from ..core.md_io import MarkdownDocument, read_markdown, write_markdown
from ..core.time import format_utc_iso8601, parse_utc_iso8601

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "MigrationResult",
    "MigrationStats",
    "migrate_file",
    "migrate_vault",
    "validate_migration",
]


@dataclass
class MigrationResult:
    """Result of migrating a single file.

    Attributes
    ----------
    file_path : Path
        Path to the file
    success : bool
        Whether migration succeeded
    changes : list[str]
        List of changes made
    errors : list[str]
        List of errors encountered
    """

    file_path: Path
    success: bool
    changes: list[str]
    errors: list[str]

    def add_change(self, change: str) -> None:
        """Add a change description."""
        self.changes.append(change)

    def add_error(self, error: str) -> None:
        """Add an error."""
        self.errors.append(error)
        self.success = False


@dataclass
class MigrationStats:
    """Statistics for vault migration.

    Attributes
    ----------
    total_files : int
        Total files processed
    successful : int
        Successfully migrated
    failed : int
        Failed migrations
    skipped : int
        Skipped (already migrated)
    """

    total_files: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0

    def add_result(self, result: MigrationResult) -> None:
        """Add a migration result to stats."""
        self.total_files += 1
        if result.success:
            if result.changes:
                self.successful += 1
            else:
                self.skipped += 1
        else:
            self.failed += 1


def normalize_timestamp_to_utc(timestamp_str: str) -> str | None:
    """Convert timestamp to UTC ISO-8601 format.

    Handles various input formats:
    - ISO-8601 with timezone
    - ISO-8601 without timezone (assumes local)
    - Unix timestamps
    - Date-only strings

    Parameters
    ----------
    timestamp_str
        Timestamp string in various formats

    Returns
    -------
    str | None
        UTC ISO-8601 timestamp or None if invalid
    """
    if not timestamp_str:
        return None

    try:
        # Try parsing as ISO-8601
        dt = parse_utc_iso8601(timestamp_str)
        return format_utc_iso8601(dt)
    except (ValueError, AttributeError):
        pass

    # Try other common formats
    try:
        # Unix timestamp
        if timestamp_str.isdigit():
            dt = datetime.fromtimestamp(int(timestamp_str), tz=UTC)
            return format_utc_iso8601(dt)
    except (ValueError, OSError):
        pass

    try:
        # Date-only (YYYY-MM-DD)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", timestamp_str):
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d")
            dt = dt.replace(tzinfo=UTC)
            return format_utc_iso8601(dt)
    except ValueError:
        pass

    return None


def infer_entity_type(file_path: Path, metadata: dict[str, Any]) -> str:
    """Infer entity type from file path and metadata.

    Parameters
    ----------
    file_path
        Path to the file
    metadata
        Front-matter metadata

    Returns
    -------
    str
        Entity type ("task", "note", or "event")
    """
    # Check metadata for explicit type
    if "type" in metadata:
        entity_type = metadata["type"].lower()
        if entity_type in ("task", "note", "event"):
            return entity_type

    # Infer from file path
    path_str = str(file_path).lower()

    if "task" in path_str or "todo" in path_str:
        return "task"
    if "event" in path_str or "calendar" in path_str:
        return "event"
    return "note"  # Default


def migrate_file(
    file_path: Path,
    dry_run: bool = False,
) -> MigrationResult:
    """Migrate a single file to new schema (Phase 8, Point 23).

    DoD: Add missing UIDs, normalize schema, convert timestamps to UTC.

    Parameters
    ----------
    file_path
        Path to file to migrate
    dry_run
        If True, don't write changes

    Returns
    -------
    MigrationResult
        Migration result with changes and errors
    """
    result = MigrationResult(
        file_path=file_path,
        success=True,
        changes=[],
        errors=[],
    )

    try:
        # Read file
        doc = read_markdown(file_path)
        metadata = doc.frontmatter.copy()

        # Infer entity type
        entity_type = infer_entity_type(file_path, metadata)

        # 1. Add/normalize UID
        if "id" not in metadata and "uid" not in metadata:
            # Generate new UID
            title = str(metadata.get("title", file_path.stem))
            new_id = generate_entity_id(entity_type, title=title)
            metadata["id"] = new_id
            result.add_change(f"Added UID: {new_id}")
        elif "uid" in metadata and "id" not in metadata:
            # Rename uid → id
            metadata["id"] = metadata.pop("uid")
            result.add_change("Renamed 'uid' to 'id'")

        # 2. Normalize timestamps to UTC
        timestamp_fields = [
            "created",
            "updated",
            "created_ts",
            "updated_ts",
            "due",
            "due_ts",
            "start_ts",
            "done_ts",
        ]

        for field in timestamp_fields:
            if field in metadata:
                original = metadata[field]
                normalized = normalize_timestamp_to_utc(str(original))

                if normalized and normalized != original:
                    metadata[field] = normalized
                    result.add_change(f"Normalized {field}: {original} → {normalized}")

        # 3. Ensure required fields
        now_utc = format_utc_iso8601(datetime.now(UTC))

        if "created" not in metadata:
            metadata["created"] = now_utc
            result.add_change("Added 'created' timestamp")

        if "updated" not in metadata:
            metadata["updated"] = now_utc
            result.add_change("Added 'updated' timestamp")

        # 4. Normalize tags (ensure list)
        if "tags" in metadata:
            if isinstance(metadata["tags"], str):
                # Convert comma-separated string to list
                metadata["tags"] = [t.strip() for t in str(metadata["tags"]).split(",")]
                result.add_change("Normalized tags to list")
        elif entity_type in ("task", "note"):
            # Add empty tags list
            metadata["tags"] = []
            result.add_change("Added empty tags list")

        # 5. Add status for tasks
        if entity_type == "task" and "status" not in metadata:
            metadata["status"] = "todo"
            result.add_change("Added default status: todo")

        # 6. Normalize title
        if "title" not in metadata:
            metadata["title"] = str(file_path.stem)
            result.add_change(f"Added title: {file_path.stem}")

        # Write migrated file (if not dry run and changes made)
        if not dry_run and result.changes:
            migrated_doc = MarkdownDocument(
                frontmatter=metadata,
                content=doc.content,
            )
            write_markdown(file_path, migrated_doc, fsync=True)

    except Exception as e:
        result.add_error(f"Migration failed: {e!s}")

    return result


def migrate_vault(
    vault_path: Path,
    dry_run: bool = False,
    recursive: bool = True,
) -> tuple[MigrationStats, list[MigrationResult]]:
    """Migrate all files in vault (Phase 8, Point 23).

    DoD: Post-migration, every file parses and passes round-trip tests.

    Parameters
    ----------
    vault_path
        Path to vault directory
    dry_run
        If True, don't write changes
    recursive
        If True, migrate subdirectories

    Returns
    -------
    tuple[MigrationStats, list[MigrationResult]]
        Statistics and individual results
    """
    stats = MigrationStats()
    results: list[MigrationResult] = []

    # Find all .md files
    md_files = list(vault_path.rglob("*.md")) if recursive else list(vault_path.glob("*.md"))

    # Migrate each file
    for md_file in md_files:
        result = migrate_file(md_file, dry_run=dry_run)
        results.append(result)
        stats.add_result(result)

    return stats, results


def validate_migration(file_path: Path) -> tuple[bool, list[str]]:
    """Validate that migrated file passes round-trip test.

    DoD: Post-migration, every file parses and passes round-trip tests.

    Parameters
    ----------
    file_path
        Path to file to validate

    Returns
    -------
    tuple[bool, list[str]]
        (is_valid, errors)
    """
    errors = []

    try:
        # Parse file
        doc = read_markdown(file_path)

        # Check required fields
        required_fields = ["id", "title", "created", "updated"]
        for field in required_fields:
            if field not in doc.frontmatter:
                errors.append(f"Missing required field: {field}")

        # Validate timestamps are UTC ISO-8601
        timestamp_fields = ["created", "updated", "due", "start_ts", "done_ts"]
        for field in timestamp_fields:
            if field in doc.frontmatter:
                try:
                    ts = doc.frontmatter[field]
                    if isinstance(ts, str):
                        parse_utc_iso8601(ts)
                except Exception as e:
                    errors.append(f"Invalid timestamp in {field}: {e}")

        # Round-trip test: serialize → parse → equal
        from io import StringIO

        import yaml

        serialized = yaml.dump(doc.frontmatter, default_flow_style=False, allow_unicode=True)
        reparsed = yaml.safe_load(StringIO(serialized))

        if reparsed != doc.frontmatter:
            errors.append("Round-trip test failed: metadata changed after serialize/parse")

    except Exception as e:
        errors.append(f"Validation failed: {e!s}")

    return len(errors) == 0, errors
