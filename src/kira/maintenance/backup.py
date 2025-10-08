"""Vault backup utilities (Phase 10, Point 27).

Regular Vault backups with restore capability.
"""

from __future__ import annotations

import shutil
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "BackupConfig",
    "BackupInfo",
    "create_backup",
    "restore_backup",
    "list_backups",
    "cleanup_old_backups",
]


@dataclass
class BackupConfig:
    """Backup configuration.
    
    Attributes
    ----------
    backup_dir : Path
        Directory to store backups
    retention_count : int
        Number of backups to keep (default: 7)
    compress : bool
        Whether to compress backups (default: True)
    """
    
    backup_dir: Path
    retention_count: int = 7
    compress: bool = True


@dataclass
class BackupInfo:
    """Information about a backup.
    
    Attributes
    ----------
    backup_path : Path
        Path to backup file
    timestamp : datetime
        When backup was created
    size_bytes : int
        Size of backup in bytes
    vault_path : Path | None
        Original vault path (if known)
    """
    
    backup_path: Path
    timestamp: datetime
    size_bytes: int
    vault_path: Path | None = None


def create_backup(
    vault_path: Path,
    config: BackupConfig,
) -> BackupInfo:
    """Create vault backup (Phase 10, Point 27).
    
    DoD: Backup created successfully.
    
    Parameters
    ----------
    vault_path
        Path to vault to backup
    config
        Backup configuration
        
    Returns
    -------
    BackupInfo
        Information about created backup
    """
    # Ensure backup directory exists
    config.backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now(timezone.utc)
    timestamp_str = timestamp.strftime("%Y%m%d-%H%M%S")
    
    if config.compress:
        backup_filename = f"vault-backup-{timestamp_str}.tar.gz"
    else:
        backup_filename = f"vault-backup-{timestamp_str}.tar"
    
    backup_path = config.backup_dir / backup_filename
    
    # Create tar archive
    with tarfile.open(backup_path, f"w:{'gz' if config.compress else ''}") as tar:
        # Add all files from vault
        tar.add(vault_path, arcname=vault_path.name)
    
    # Get backup size
    size_bytes = backup_path.stat().st_size
    
    return BackupInfo(
        backup_path=backup_path,
        timestamp=timestamp,
        size_bytes=size_bytes,
        vault_path=vault_path,
    )


def restore_backup(
    backup_path: Path,
    restore_path: Path,
    overwrite: bool = False,
) -> Path:
    """Restore vault from backup (Phase 10, Point 27).
    
    DoD: Backup/restore tested.
    
    Parameters
    ----------
    backup_path
        Path to backup file
    restore_path
        Path to restore vault to
    overwrite
        Whether to overwrite existing vault
        
    Returns
    -------
    Path
        Path to restored vault
        
    Raises
    ------
    FileExistsError
        If restore_path exists and overwrite=False
    """
    if restore_path.exists() and not overwrite:
        raise FileExistsError(f"Restore path exists: {restore_path}")
    
    # Remove existing if overwrite
    if restore_path.exists() and overwrite:
        if restore_path.is_dir():
            shutil.rmtree(restore_path)
        else:
            restore_path.unlink()
    
    # Create parent directory
    restore_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract tar archive
    with tarfile.open(backup_path, "r:*") as tar:
        # Get the root directory name before closing
        root_name = tar.getnames()[0].split('/')[0]
        # Extract to parent directory
        tar.extractall(restore_path.parent, filter='data')
    
    # Tar extracts to original name, rename if needed
    extracted_path = restore_path.parent / root_name
    
    if extracted_path != restore_path:
        extracted_path.rename(restore_path)
    
    return restore_path


def list_backups(backup_dir: Path) -> list[BackupInfo]:
    """List all backups in directory.
    
    Parameters
    ----------
    backup_dir
        Directory containing backups
        
    Returns
    -------
    list[BackupInfo]
        List of backups, sorted by timestamp (newest first)
    """
    if not backup_dir.exists():
        return []
    
    backups = []
    
    for backup_file in backup_dir.glob("vault-backup-*.tar*"):
        # Parse timestamp from filename
        # Format: vault-backup-YYYYMMDD-HHMMSS.tar.gz
        try:
            name = backup_file.stem
            if name.endswith('.tar'):
                name = name[:-4]
            
            timestamp_str = name.split('-')[-2] + '-' + name.split('-')[-1]
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d-%H%M%S")
            timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            size_bytes = backup_file.stat().st_size
            
            backups.append(BackupInfo(
                backup_path=backup_file,
                timestamp=timestamp,
                size_bytes=size_bytes,
            ))
        except (ValueError, IndexError):
            # Skip files with unexpected format
            continue
    
    # Sort by timestamp, newest first
    backups.sort(key=lambda b: b.timestamp, reverse=True)
    
    return backups


def cleanup_old_backups(
    backup_dir: Path,
    retention_count: int = 7,
) -> int:
    """Delete old backups, keeping only recent ones.
    
    DoD: Storage usage stays bounded.
    
    Parameters
    ----------
    backup_dir
        Directory containing backups
    retention_count
        Number of backups to keep
        
    Returns
    -------
    int
        Number of backups deleted
    """
    backups = list_backups(backup_dir)
    
    # Keep only retention_count newest
    to_delete = backups[retention_count:]
    
    for backup in to_delete:
        backup.backup_path.unlink()
    
    return len(to_delete)
