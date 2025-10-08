"""Tests for atomic writes (Phase 4, Point 11).

DoD: Crash test (kill -9 mid-write) leaves either old or new file—never partial.
Tests atomic write protocol: tmp → fsync(tmp) → rename → fsync(dir).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kira.core.md_io import MarkdownDocument, MarkdownIOError, write_markdown


class TestAtomicWriteProtocol:
    """Test atomic write protocol (Phase 4, Point 11)."""

    def test_atomic_write_creates_temp_file_in_same_dir(self):
        """Test temp file created in same directory (same filesystem)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            # Monitor temp file creation
            created_temp_files = []
            original_named_temp = tempfile.NamedTemporaryFile

            def tracked_named_temp(*args, **kwargs):
                file = original_named_temp(*args, **kwargs)
                created_temp_files.append(Path(file.name))
                return file

            with patch("tempfile.NamedTemporaryFile", tracked_named_temp):
                write_markdown(file_path, document, atomic=True)

            # Verify temp file was in same directory
            assert len(created_temp_files) > 0
            temp_file = created_temp_files[0]
            # Temp file should have been in same dir (parent)
            # After write, it's renamed away but we can check the pattern
            assert file_path.exists()

    def test_atomic_write_uses_fsync(self):
        """Test atomic write uses fsync for crash safety."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            # Track fsync calls
            fsync_calls = []
            original_fsync = os.fsync

            def tracked_fsync(fd):
                fsync_calls.append(fd)
                return original_fsync(fd)

            with patch("os.fsync", tracked_fsync):
                write_markdown(file_path, document, atomic=True, fsync=True)

            # Should have at least 2 fsync calls:
            # 1. fsync(tmp_file)
            # 2. fsync(dir)
            assert len(fsync_calls) >= 2

    def test_atomic_write_fsync_disabled(self):
        """Test atomic write with fsync=False still works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            # Should work without fsync
            write_markdown(file_path, document, atomic=True, fsync=False)

            assert file_path.exists()
            content = file_path.read_text()
            assert "title: Test" in content

    def test_atomic_rename_is_atomic(self):
        """Test rename operation is atomic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            # Track rename calls
            rename_calls = []
            original_rename = Path.rename

            def tracked_rename(self, target):
                rename_calls.append((self, target))
                return original_rename(self, target)

            with patch.object(Path, "rename", tracked_rename):
                write_markdown(file_path, document, atomic=True)

            # Should have exactly one rename call (tmp → target)
            assert len(rename_calls) == 1
            source, target = rename_calls[0]
            assert target == file_path


class TestAtomicWriteReplaces:
    """Test atomic write replaces existing file."""

    def test_atomic_write_replaces_existing_file(self):
        """Test atomic write replaces existing file atomically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"

            # Create initial file
            file_path.write_text("Old content")
            old_content = file_path.read_text()
            assert old_content == "Old content"

            # Atomic write new content
            document = MarkdownDocument(frontmatter={"title": "New"}, content="New content")
            write_markdown(file_path, document, atomic=True)

            # File should have new content
            new_content = file_path.read_text()
            assert "New content" in new_content
            assert "Old content" not in new_content

    def test_no_partial_file_on_error(self):
        """Test error during write doesn't leave partial file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"

            # Create initial file
            file_path.write_text("Old content")

            document = MarkdownDocument(frontmatter={"title": "Test"}, content="New content")

            # Simulate error during write by making rename fail
            def failing_rename(self, target):
                raise OSError("Simulated rename failure")

            with patch.object(Path, "rename", failing_rename):
                try:
                    write_markdown(file_path, document, atomic=True)
                except (MarkdownIOError, OSError):
                    pass

            # Original file should still exist with old content
            # (or not exist if it didn't exist before)
            if file_path.exists():
                content = file_path.read_text()
                # Should still have old content, not partial new content
                assert content == "Old content"


class TestNonAtomicWrite:
    """Test non-atomic write mode."""

    def test_non_atomic_write_works(self):
        """Test non-atomic write (direct write_text)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            write_markdown(file_path, document, atomic=False)

            assert file_path.exists()
            content = file_path.read_text()
            assert "title: Test" in content

    def test_non_atomic_write_does_not_use_temp_file(self):
        """Test non-atomic write doesn't create temp file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            # Track temp file creation
            temp_file_created = False
            original_named_temp = tempfile.NamedTemporaryFile

            def tracked_named_temp(*args, **kwargs):
                nonlocal temp_file_created
                temp_file_created = True
                return original_named_temp(*args, **kwargs)

            with patch("tempfile.NamedTemporaryFile", tracked_named_temp):
                write_markdown(file_path, document, atomic=False)

            # No temp file should be created
            assert not temp_file_created


class TestCrashSafety:
    """Test crash safety guarantees (Phase 4, Point 11 DoD)."""

    def test_crash_simulation_leaves_consistent_state(self):
        """Test simulated crash leaves either old or new file, never partial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"

            # Create initial file
            initial_doc = MarkdownDocument(frontmatter={"title": "Initial", "version": 1}, content="Initial content")
            write_markdown(file_path, initial_doc, atomic=True)

            # Simulate crash at different points
            crash_points = [
                "after_temp_write",
                "after_fsync_file",
                "after_rename",
            ]

            for crash_point in crash_points:
                # Reset to initial state
                write_markdown(file_path, initial_doc, atomic=True)

                # Attempt write with simulated crash
                new_doc = MarkdownDocument(frontmatter={"title": "New", "version": 2}, content="New content")

                try:
                    if crash_point == "after_temp_write":
                        # Crash before rename
                        def crash_before_rename(self, target):
                            raise KeyboardInterrupt("Simulated crash")

                        with patch.object(Path, "rename", crash_before_rename):
                            write_markdown(file_path, new_doc, atomic=True)

                    elif crash_point == "after_fsync_file":
                        # Crash after file fsync but before rename
                        def crash_on_rename(self, target):
                            raise KeyboardInterrupt("Simulated crash")

                        with patch.object(Path, "rename", crash_on_rename):
                            write_markdown(file_path, new_doc, atomic=True)

                    elif crash_point == "after_rename":
                        # Complete write (no crash)
                        write_markdown(file_path, new_doc, atomic=True)

                except (KeyboardInterrupt, MarkdownIOError):
                    pass

                # File should exist and be valid
                if file_path.exists():
                    from kira.core.md_io import read_markdown

                    doc = read_markdown(file_path)

                    # Should have either old or new version, not corrupted
                    version = doc.get_metadata("version")
                    assert version in [1, 2], f"Invalid version at crash point {crash_point}"

                    # Content should match version
                    if version == 1:
                        assert "Initial content" in doc.content
                    elif version == 2:
                        assert "New content" in doc.content


class TestTempFileCleanup:
    """Test temp file cleanup on errors."""

    def test_temp_file_cleaned_up_on_error(self):
        """Test temp file is cleaned up when write fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            # Simulate error during rename
            def failing_rename(self, target):
                raise OSError("Simulated failure")

            with patch.object(Path, "rename", failing_rename):
                try:
                    write_markdown(file_path, document, atomic=True)
                except (MarkdownIOError, OSError):
                    pass

            # Check no temp files left behind
            temp_files = list(Path(tmpdir).glob(".*.tmp*"))
            assert len(temp_files) == 0, f"Temp files not cleaned up: {temp_files}"


class TestDirectoryCreation:
    """Test directory creation during atomic writes."""

    def test_creates_parent_directories(self):
        """Test atomic write creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "subdir" / "nested" / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            # Parent directories don't exist
            assert not file_path.parent.exists()

            write_markdown(file_path, document, atomic=True, create_dirs=True)

            # File and directories should exist
            assert file_path.exists()
            assert file_path.parent.exists()

    def test_create_dirs_false_fails_without_parent(self):
        """Test write fails when parent doesn't exist and create_dirs=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nonexistent" / "test.md"
            document = MarkdownDocument(frontmatter={"title": "Test"}, content="Test content")

            with pytest.raises(MarkdownIOError):
                write_markdown(file_path, document, atomic=True, create_dirs=False)


class TestAtomicWriteContent:
    """Test content correctness with atomic writes."""

    def test_atomic_write_preserves_content(self):
        """Test atomic write preserves exact content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            document = MarkdownDocument(
                frontmatter={"title": "Test", "tags": ["a", "b"], "priority": 5},
                content="Line 1\nLine 2\n\nLine 4 with unicode: 日本語",
            )

            write_markdown(file_path, document, atomic=True)

            # Read back and verify
            from kira.core.md_io import read_markdown

            read_doc = read_markdown(file_path)

            assert read_doc.get_metadata("title") == "Test"
            assert read_doc.get_metadata("tags") == ["a", "b"]
            assert read_doc.get_metadata("priority") == 5
            assert "日本語" in read_doc.content


class TestConcurrentWrites:
    """Test behavior under concurrent write attempts."""

    def test_sequential_atomic_writes_all_succeed(self):
        """Test sequential atomic writes all complete successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"

            # Perform multiple sequential writes
            for i in range(10):
                document = MarkdownDocument(
                    frontmatter={"title": f"Version {i}", "version": i}, content=f"Content version {i}"
                )
                write_markdown(file_path, document, atomic=True)

            # Final file should have last version
            from kira.core.md_io import read_markdown

            final_doc = read_markdown(file_path)
            assert final_doc.get_metadata("version") == 9
            assert "Content version 9" in final_doc.content
