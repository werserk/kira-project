"""Vault storage layer with atomic writes and file locking (Phase 0, Point 2).

SINGLE WRITER PATTERN (Phase 0 Definition of Done):
====================================================
This module implements the Single Writer pattern:
- ALL vault entity mutations MUST go through this layer
- NO direct `open(..., 'w')` allowed outside this module for vault entities
- NO direct file.write_text() for vault entities outside this module
- Route: CLI/Plugins/Adapters → HostAPI → vault.py → md_io.py

Enforcement verified by: grep -r "open(.*'w'" src/kira/{cli,plugins,adapters}
DoD: Zero offenders outside vault.py for entity writes.

This module provides:
- Per-entity file locking to prevent concurrent write conflicts
- Atomic file writes (temp file + rename) for crash safety
- Single interface for all Vault mutations
- Integration with HostAPI for validation and event emission

Acceptable file writes OUTSIDE this module:
- System files (config, logs, quarantine, caches)
- Report/artifact generation (validation reports, backups)
- Plugin-specific storage (not vault entities)
"""

from __future__ import annotations

import fcntl
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.host import Entity, EntityNotFoundError, HostAPI, VaultError, create_host_api
from ..core.md_io import MarkdownDocument, MarkdownIOError, read_markdown

__all__ = [
    "Vault",
    "VaultConfig",
    "get_vault",
]


@dataclass
class VaultConfig:
    """Configuration for Vault storage."""

    vault_path: Path
    enable_file_locks: bool = True
    lock_timeout: float = 10.0  # seconds


class Vault:
    """Single Writer storage layer with file locking.

    This class enforces the Single Writer pattern (Phase 0, Point 1):
    - All mutations go through this layer
    - Per-entity file locks prevent concurrent writes
    - Atomic writes ensure crash safety
    - Integration with HostAPI for validation

    Example:
        >>> vault = Vault(VaultConfig(vault_path=Path("vault")))
        >>> entity = vault.upsert(entity_type="task", data={"title": "My Task"})
        >>> retrieved = vault.get(entity.id)
        >>> vault.delete(entity.id)
    """

    def __init__(self, config: VaultConfig) -> None:
        """Initialize Vault storage.

        Parameters
        ----------
        config
            Vault configuration
        """
        self.config = config
        self.vault_path = config.vault_path
        
        # Create HostAPI for validation and event emission
        self.host_api = create_host_api(self.vault_path)
        
        # File lock handles (uid -> file handle)
        self._locks: dict[str, int] = {}

    def get(self, uid: str) -> Entity:
        """Read entity by UID.

        Parameters
        ----------
        uid
            Entity unique identifier

        Returns
        -------
        Entity
            Entity data

        Raises
        ------
        EntityNotFoundError
            If entity not found
        VaultError
            If read fails
        """
        return self.host_api.read_entity(uid)

    def upsert(
        self,
        entity_type: str,
        data: dict[str, Any],
        *,
        content: str = "",
    ) -> Entity:
        """Create or update entity (Single Writer pattern).

        This is the ONLY method that should be used for mutations.
        All CLI commands, plugins, and adapters MUST route through this.

        Parameters
        ----------
        entity_type
            Type of entity (task, note, event, etc.)
        data
            Entity metadata
        content
            Markdown content body

        Returns
        -------
        Entity
            Created or updated entity

        Raises
        ------
        VaultError
            If operation fails
        """
        # Extract or generate entity ID
        entity_id = data.get("id")
        if not entity_id:
            # Let HostAPI generate ID
            pass
        
        # Acquire file lock for this entity
        with self._acquire_entity_lock(entity_id) if entity_id else self._no_lock():
            # Delegate to HostAPI for validation and event emission
            # HostAPI will handle atomic writes via md_io.write_markdown(atomic=True)
            entity = self.host_api.upsert_entity(entity_type, data, content=content)
            
            return entity

    def delete(self, uid: str) -> None:
        """Delete entity by UID.

        Parameters
        ----------
        uid
            Entity unique identifier

        Raises
        ------
        EntityNotFoundError
            If entity not found
        VaultError
            If deletion fails
        """
        with self._acquire_entity_lock(uid):
            self.host_api.delete_entity(uid)

    def list_entities(
        self,
        entity_type: str | None = None,
        *,
        limit: int | None = None,
    ) -> list[Entity]:
        """List entities in Vault.

        Parameters
        ----------
        entity_type
            Optional filter by entity type
        limit
            Optional maximum number of entities to return

        Returns
        -------
        list[Entity]
            List of entities
        """
        return list(self.host_api.list_entities(entity_type, limit=limit))

    def atomic_write(
        self,
        file_path: Path,
        content: str,
        *,
        create_dirs: bool = True,
    ) -> None:
        """Atomic file write helper (temp file + rename + fsync).

        Phase 0 requirement: atomic writes with crash safety.

        Parameters
        ----------
        file_path
            Target file path
        content
            Content to write
        create_dirs
            Create parent directories if needed

        Raises
        ------
        VaultError
            If write fails
        """
        try:
            # Create parent directories
            if create_dirs and not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file on same filesystem
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=file_path.parent,
                prefix=f".{file_path.name}.tmp",
                delete=False,
            ) as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                # Fsync to ensure data reaches disk
                os.fsync(tmp_file.fileno())
                tmp_path = Path(tmp_file.name)

            # Atomic rename
            tmp_path.rename(file_path)
            
            # Fsync directory to ensure rename is persisted
            dir_fd = os.open(file_path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

        except Exception as exc:
            raise VaultError(f"Atomic write failed for {file_path}: {exc}") from exc

    def _acquire_entity_lock(self, entity_id: str) -> EntityLock:
        """Acquire file lock for entity.

        Parameters
        ----------
        entity_id
            Entity identifier

        Returns
        -------
        EntityLock
            Lock context manager
        """
        if not self.config.enable_file_locks:
            return self._no_lock()
        
        return EntityLock(self, entity_id, self.config.lock_timeout)

    def _no_lock(self) -> NoOpLock:
        """Return no-op lock context manager."""
        return NoOpLock()


class EntityLock:
    """Per-entity file lock context manager (Phase 0, Point 1)."""

    def __init__(self, vault: Vault, entity_id: str, timeout: float) -> None:
        """Initialize entity lock.

        Parameters
        ----------
        vault
            Vault instance
        entity_id
            Entity identifier to lock
        timeout
            Lock acquisition timeout
        """
        self.vault = vault
        self.entity_id = entity_id
        self.timeout = timeout
        self.lock_file: Path | None = None
        self.lock_fd: int | None = None

    def __enter__(self) -> EntityLock:
        """Acquire lock."""
        # Create locks directory
        locks_dir = self.vault.vault_path / ".kira" / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        
        # Create lock file for this entity
        # Use entity ID as filename (safe since IDs are validated)
        lock_filename = self.entity_id.replace("/", "_")
        self.lock_file = locks_dir / f"{lock_filename}.lock"
        
        # Open lock file
        self.lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR, 0o644)
        
        # Acquire exclusive lock (with timeout via LOCK_NB + retry)
        import time
        start_time = time.time()
        
        while True:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break  # Lock acquired
            except BlockingIOError:
                # Lock held by another process
                if time.time() - start_time > self.timeout:
                    os.close(self.lock_fd)
                    raise VaultError(
                        f"Failed to acquire lock for entity {self.entity_id} "
                        f"after {self.timeout}s timeout"
                    )
                time.sleep(0.05)  # Wait 50ms before retry
        
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Release lock."""
        if self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
            except Exception:
                pass  # Best effort cleanup
            
            self.lock_fd = None


class NoOpLock:
    """No-op lock for when locking is disabled."""

    def __enter__(self) -> NoOpLock:
        """Enter context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        pass


# Global Vault instance
_global_vault: Vault | None = None


def get_vault(config: VaultConfig | None = None) -> Vault:
    """Get global Vault instance.

    Parameters
    ----------
    config
        Optional configuration (creates new instance if provided)

    Returns
    -------
    Vault
        Global Vault instance
    """
    global _global_vault

    if config is not None or _global_vault is None:
        if config is None:
            # Default configuration
            from ..core.config import load_config
            
            cfg = load_config()
            vault_path = Path(cfg.get("vault", {}).get("path", "vault"))
            config = VaultConfig(vault_path=vault_path)
        
        _global_vault = Vault(config)

    return _global_vault

