"""Integration tests for Phase 4 requirements (Migration & Compatibility).

Phase 4 DoD:
- Point 15: Vault migrator normalizes all .md, adds missing UIDs, converts timestamps to UTC
- Point 16: Migration dry-run validates in read-only mode with detailed report
"""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kira.cli.kira_migrate import main as migrate_main
from kira.core.md_io import MarkdownDocument, write_markdown
from kira.core.time import format_utc_iso8601
from kira.migration.migrator import migrate_vault, validate_migration


class TestPhase4Point15VaultMigrator:
    """Test Phase 4, Point 15: Vault migrator.

    DoD: After migration, every file parses and passes round-trip tests.
    """

    def test_migrator_adds_missing_uids(self):
        """Test migrator adds missing UIDs to files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)

            # Create file without UID
            file_path = vault_path / "test.md"
            doc = MarkdownDocument(
                frontmatter={"title": "Test File"},
                content="Content",
            )
            write_markdown(file_path, doc)

            # Migrate
            stats, results = migrate_vault(vault_path, dry_run=False)

            # Check that UID was added
            assert stats.successful == 1
            assert len(results[0].changes) > 0
            assert any("Added UID" in change for change in results[0].changes)

    def test_migrator_converts_timestamps_to_utc(self):
        """Test migrator converts timestamps to UTC."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)

            # Create file with non-UTC timestamp
            # Write raw markdown to avoid YAML auto-normalization
            file_path = vault_path / "test.md"
            raw_content = """---
title: Test
created: 2025-10-08
---
Content"""
            file_path.write_text(raw_content, encoding="utf-8")

            # Migrate
            stats, results = migrate_vault(vault_path, dry_run=False)

            # Check that timestamp was normalized
            assert stats.successful == 1
            assert any("Normalized created" in change for change in results[0].changes)

    def test_migrator_normalizes_schema(self):
        """Test migrator normalizes to new schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)

            # Create file with partial schema
            file_path = vault_path / "task.md"
            doc = MarkdownDocument(
                frontmatter={"title": "My Task"},
                content="Content",
            )
            write_markdown(file_path, doc)

            # Migrate
            stats, results = migrate_vault(vault_path, dry_run=False)

            # Should add: id, created, updated, status, tags
            assert stats.successful == 1
            changes = results[0].changes
            assert any("Added UID" in change for change in changes)
            assert any("created" in change for change in changes)
            assert any("updated" in change for change in changes)

    def test_dod_round_trip_after_migration(self):
        """Test DoD: After migration, every file passes round-trip tests."""
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

            # Migrate
            _stats, results = migrate_vault(vault_path, dry_run=False)

            # All files should pass validation (round-trip test)
            for result in results:
                if result.success and result.changes:
                    is_valid, errors = validate_migration(result.file_path)
                    assert is_valid, f"Round-trip failed for {result.file_path}: {errors}"


class TestPhase4Point16MigrationDryRun:
    """Test Phase 4, Point 16: Migration dry-run.

    DoD: Report shows 0 critical errors before live run.
    """

    def test_dry_run_does_not_modify_files(self):
        """Test dry-run mode does not modify files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)

            # Create file
            file_path = vault_path / "test.md"
            doc = MarkdownDocument(
                frontmatter={"title": "Test"},
                content="Original content",
            )
            write_markdown(file_path, doc)

            original_mtime = file_path.stat().st_mtime

            # Run dry-run migration
            _stats, results = migrate_vault(vault_path, dry_run=True)

            # File should not be modified
            assert file_path.stat().st_mtime == original_mtime

            # But changes should be reported
            assert len(results[0].changes) > 0

    def test_dry_run_validation_report(self):
        """Test dry-run produces detailed validation report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)

            # Create files
            file1 = vault_path / "valid.md"
            doc1 = MarkdownDocument(
                frontmatter={
                    "id": "note-123",
                    "title": "Valid",
                    "created": format_utc_iso8601(datetime.now(UTC)),
                    "updated": format_utc_iso8601(datetime.now(UTC)),
                    "tags": [],
                },
                content="Content",
            )
            write_markdown(file1, doc1)

            file2 = vault_path / "needs_migration.md"
            doc2 = MarkdownDocument(
                frontmatter={"title": "Needs Migration"},
                content="Content",
            )
            write_markdown(file2, doc2)

            # Run dry-run migration
            stats, results = migrate_vault(vault_path, dry_run=True)

            # Should report what needs to be migrated
            assert stats.total_files == 2

            # Find result for file that needs migration
            needs_migration_result = next(r for r in results if "needs_migration" in str(r.file_path))
            assert len(needs_migration_result.changes) > 0

    def test_dod_zero_critical_errors(self):
        """Test DoD: Report shows 0 critical errors before live run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)

            # Create valid files
            for i in range(3):
                file_path = vault_path / f"file{i}.md"
                doc = MarkdownDocument(
                    frontmatter={"title": f"File {i}"},
                    content=f"Content {i}",
                )
                write_markdown(file_path, doc)

            # Run dry-run migration
            stats, _results = migrate_vault(vault_path, dry_run=True)

            # Count critical errors (files that failed)
            critical_errors = stats.failed

            # DoD: 0 critical errors
            assert critical_errors == 0, f"DoD failed: {critical_errors} critical errors found"


class TestPhase4CLIIntegration:
    """Test Phase 4 CLI integration."""

    def test_cli_dry_run_flag(self, tmp_path):
        """Test CLI --dry-run flag works."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create file
        file_path = vault_path / "test.md"
        doc = MarkdownDocument(
            frontmatter={"title": "Test"},
            content="Content",
        )
        write_markdown(file_path, doc)

        # Run CLI with --dry-run
        exit_code = migrate_main(["run", "--vault-path", str(vault_path), "--dry-run"])

        # Should succeed
        assert exit_code == 0

        # File should not be modified (still missing required fields)
        from kira.core.md_io import read_markdown

        doc_after = read_markdown(file_path)
        assert "id" not in doc_after.frontmatter  # Should not have UID yet

    def test_cli_json_output(self, tmp_path, capsys):
        """Test CLI --json flag produces machine-readable output."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create file
        file_path = vault_path / "test.md"
        doc = MarkdownDocument(
            frontmatter={"title": "Test"},
            content="Content",
        )
        write_markdown(file_path, doc)

        # Run CLI with --json
        exit_code = migrate_main(["run", "--vault-path", str(vault_path), "--json", "--dry-run"])

        # Should succeed
        assert exit_code == 0

        # Capture output
        captured = capsys.readouterr()

        # Should be valid JSON
        output = json.loads(captured.out)

        # Should have expected structure
        assert "status" in output
        assert "stats" in output
        assert "results" in output
        assert output["stats"]["total_files"] == 1

    def test_cli_validate_command(self, tmp_path):
        """Test CLI validate command."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create valid file
        file_path = vault_path / "test.md"
        doc = MarkdownDocument(
            frontmatter={
                "id": "note-123",
                "title": "Test",
                "created": format_utc_iso8601(datetime.now(UTC)),
                "updated": format_utc_iso8601(datetime.now(UTC)),
                "tags": [],
            },
            content="Content",
        )
        write_markdown(file_path, doc)

        # Run validate command
        exit_code = migrate_main(["validate", "--vault-path", str(vault_path)])

        # Should succeed (0 critical errors)
        assert exit_code == 0

    def test_cli_exit_codes(self, tmp_path):
        """Test CLI returns proper exit codes."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Test with valid vault
        file_path = vault_path / "test.md"
        doc = MarkdownDocument(
            frontmatter={"title": "Test"},
            content="Content",
        )
        write_markdown(file_path, doc)

        exit_code = migrate_main(["run", "--vault-path", str(vault_path), "--dry-run"])
        assert exit_code == 0

        # Test with non-existent vault
        exit_code = migrate_main(["run", "--vault-path", "/nonexistent/path", "--dry-run"])
        assert exit_code == 5  # I/O error


class TestPhase4EndToEnd:
    """End-to-end test for Phase 4 complete workflow."""

    def test_complete_migration_workflow(self, tmp_path):
        """Test complete migration workflow: dry-run → validate → migrate → verify."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create files with various issues
        files = [
            ("old_task.md", {"title": "Old Task", "status": "todo"}),
            ("old_note.md", {"title": "Old Note", "created": "2025-10-08"}),
            ("mixed.md", {"title": "Mixed", "id": "mixed-123", "tags": "one,two"}),
        ]

        for filename, metadata in files:
            file_path = vault_path / filename
            doc = MarkdownDocument(frontmatter=metadata, content="Content")
            write_markdown(file_path, doc)

        # Step 1: Dry-run (DoD: 0 critical errors)
        stats, results = migrate_vault(vault_path, dry_run=True)
        assert stats.failed == 0, "DoD failed: dry-run found critical errors"

        # Step 2: Validate before migration
        exit_code = migrate_main(["validate", "--vault-path", str(vault_path)])
        # May fail because files need migration, but should not crash
        assert exit_code in (0, 2)

        # Step 3: Migrate
        stats, results = migrate_vault(vault_path, dry_run=False)
        assert stats.failed == 0
        assert stats.successful == len(files)

        # Step 4: Verify (DoD: every file passes round-trip)
        for result in results:
            if result.success and result.changes:
                is_valid, errors = validate_migration(result.file_path)
                assert is_valid, f"DoD failed: {result.file_path} failed round-trip: {errors}"

        # Step 5: Validate after migration
        exit_code = migrate_main(["validate", "--vault-path", str(vault_path)])
        assert exit_code == 0, "DoD failed: validation after migration should pass"


# Mark slow tests
pytestmark = pytest.mark.integration
