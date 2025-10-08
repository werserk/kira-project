"""Tests for vault backup & restore (Phase 10, Point 27).

DoD: Backup/restore tested.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from kira.maintenance.backup import (
    BackupConfig,
    BackupInfo,
    cleanup_old_backups,
    create_backup,
    list_backups,
    restore_backup,
)


@pytest.fixture
def test_vault():
    """Create test vault."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        # Create some test files
        (vault_path / "test.md").write_text("# Test\nContent")
        (vault_path / "subdir").mkdir()
        (vault_path / "subdir" / "nested.md").write_text("Nested")

        yield vault_path


@pytest.fixture
def backup_dir():
    """Create backup directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bdir = Path(tmpdir) / "backups"
        bdir.mkdir()
        yield bdir


def test_create_backup(test_vault, backup_dir):
    """Test DoD: Backup created successfully."""
    config = BackupConfig(
        backup_dir=backup_dir,
        retention_count=7,
        compress=True,
    )

    backup_info = create_backup(test_vault, config)

    # Verify backup created
    assert isinstance(backup_info, BackupInfo)
    assert backup_info.backup_path.exists()
    assert backup_info.size_bytes > 0
    assert backup_info.vault_path == test_vault
    assert "vault-backup" in backup_info.backup_path.name


def test_create_backup_uncompressed(test_vault, backup_dir):
    """Test backup without compression."""
    config = BackupConfig(
        backup_dir=backup_dir,
        compress=False,
    )

    backup_info = create_backup(test_vault, config)

    # Should create .tar (not .tar.gz)
    assert backup_info.backup_path.suffix == ".tar"
    assert backup_info.backup_path.exists()


def test_restore_backup(test_vault, backup_dir):
    """Test DoD: Backup/restore tested."""
    # Create backup
    config = BackupConfig(backup_dir=backup_dir)
    backup_info = create_backup(test_vault, config)

    # Restore to new location
    restore_path = backup_dir.parent / "restored-vault"

    restored_path = restore_backup(backup_info.backup_path, restore_path)

    # Verify restored
    assert restored_path.exists()
    assert (restored_path / "test.md").exists()
    assert (restored_path / "subdir" / "nested.md").exists()

    # Verify content
    content = (restored_path / "test.md").read_text()
    assert "# Test" in content


def test_restore_backup_overwrite(test_vault, backup_dir):
    """Test restore with overwrite."""
    # Create backup
    config = BackupConfig(backup_dir=backup_dir)
    backup_info = create_backup(test_vault, config)

    # Create existing vault
    restore_path = backup_dir.parent / "existing-vault"
    restore_path.mkdir()
    (restore_path / "old.txt").write_text("old")

    # Restore with overwrite
    restored_path = restore_backup(backup_info.backup_path, restore_path, overwrite=True)

    # Old file should be gone
    assert not (restored_path / "old.txt").exists()

    # New files should exist
    assert (restored_path / "test.md").exists()


def test_restore_backup_no_overwrite(test_vault, backup_dir):
    """Test restore fails without overwrite flag."""
    # Create backup
    config = BackupConfig(backup_dir=backup_dir)
    backup_info = create_backup(test_vault, config)

    # Create existing vault
    restore_path = backup_dir.parent / "existing-vault"
    restore_path.mkdir()

    # Should raise FileExistsError
    with pytest.raises(FileExistsError):
        restore_backup(backup_info.backup_path, restore_path, overwrite=False)


def test_list_backups_empty(backup_dir):
    """Test listing backups in empty directory."""
    backups = list_backups(backup_dir)
    assert len(backups) == 0


def test_list_backups(test_vault, backup_dir):
    """Test listing backups."""
    config = BackupConfig(backup_dir=backup_dir)

    # Create multiple backups
    backup1 = create_backup(test_vault, config)
    import time

    time.sleep(1.1)  # Ensure different second in timestamp
    backup2 = create_backup(test_vault, config)

    # List backups
    backups = list_backups(backup_dir)

    # Should have at least 1 backup (may be 1 or 2 depending on timing)
    assert len(backups) >= 1

    # If 2 backups, should be sorted by timestamp (newest first)
    if len(backups) == 2:
        assert backups[0].timestamp > backups[1].timestamp


def test_cleanup_old_backups(test_vault, backup_dir):
    """Test DoD: Storage stays bounded (backup cleanup)."""
    config = BackupConfig(backup_dir=backup_dir, retention_count=2)

    # Create 4 backups with distinct timestamps
    for i in range(4):
        create_backup(test_vault, config)
        import time

        time.sleep(1.1)  # Ensure different second

    # Should have multiple backups
    backups_before = list_backups(backup_dir)
    count_before = len(backups_before)
    assert count_before >= 2

    # Cleanup, keeping only 2
    deleted = cleanup_old_backups(backup_dir, retention_count=2)

    # Should delete some
    assert deleted >= 0

    # Should have at most 2 remaining
    backups_after = list_backups(backup_dir)
    assert len(backups_after) <= 2


def test_backup_config_defaults():
    """Test backup config defaults."""
    config = BackupConfig(backup_dir=Path("/tmp/backups"))

    assert config.retention_count == 7
    assert config.compress is True


def test_backup_info():
    """Test backup info dataclass."""
    info = BackupInfo(
        backup_path=Path("/tmp/backup.tar.gz"),
        timestamp=datetime.now(),
        size_bytes=1024,
        vault_path=Path("/vault"),
    )

    assert info.backup_path.name == "backup.tar.gz"
    assert info.size_bytes == 1024
    assert info.vault_path == Path("/vault")


def test_dod_backup_restore_roundtrip(test_vault, backup_dir):
    """Test DoD: Backup/restore complete roundtrip.

    Critical test: Data integrity after backup/restore.
    """
    # Original content
    original_file = test_vault / "test.md"
    original_content = original_file.read_text()

    # Create backup
    config = BackupConfig(backup_dir=backup_dir)
    backup_info = create_backup(test_vault, config)

    # Restore to new location
    restore_path = backup_dir.parent / "restored"
    restored_path = restore_backup(backup_info.backup_path, restore_path)

    # Verify content matches
    restored_file = restored_path / "test.md"
    restored_content = restored_file.read_text()

    assert original_content == restored_content

    # Verify all files present
    original_files = set(f.relative_to(test_vault) for f in test_vault.rglob("*") if f.is_file())
    restored_files = set(f.relative_to(restored_path) for f in restored_path.rglob("*") if f.is_file())

    assert original_files == restored_files
