"""Tests for Vault storage layer with file locking (Phase 0, Point 1)."""

import tempfile
import threading
import time
from pathlib import Path

import pytest

from kira.core.host import EntityNotFoundError
from kira.storage.vault import Vault, VaultConfig


def test_vault_get_nonexistent_entity():
    """Test reading non-existent entity raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)

        with pytest.raises(EntityNotFoundError):
            vault.get("task-20250108-1234-nonexistent")


def test_vault_upsert_create_entity():
    """Test creating new entity via upsert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)

        # Create entity
        entity = vault.upsert(entity_type="task", data={"title": "Test Task", "status": "todo"}, content="Test content")

        assert entity.id is not None
        assert entity.metadata["title"] == "Test Task"
        assert entity.metadata["status"] == "todo"
        assert entity.content == "Test content"

        # Verify it was written
        retrieved = vault.get(entity.id)
        assert retrieved.id == entity.id
        assert retrieved.metadata["title"] == "Test Task"


def test_vault_upsert_update_entity():
    """Test updating existing entity via upsert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)

        # Create entity
        entity = vault.upsert(
            entity_type="task",
            data={"title": "Original Title", "status": "todo"},
        )

        # Update via upsert
        updated = vault.upsert(
            entity_type="task",
            data={"id": entity.id, "title": "Updated Title", "status": "doing"},
            content="Updated content",
        )

        assert updated.id == entity.id
        assert updated.metadata["title"] == "Updated Title"
        assert updated.metadata["status"] == "doing"
        assert updated.content == "Updated content"


def test_vault_delete_entity():
    """Test deleting entity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)

        # Create entity
        entity = vault.upsert(
            entity_type="task",
            data={"title": "Test Task", "status": "todo"},
        )

        # Delete it
        vault.delete(entity.id)

        # Verify it's gone
        with pytest.raises(EntityNotFoundError):
            vault.get(entity.id)


def test_vault_list_entities():
    """Test listing entities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)

        # Create multiple entities
        vault.upsert(entity_type="task", data={"title": "Task 1", "status": "todo"})
        vault.upsert(entity_type="task", data={"title": "Task 2", "status": "todo"})
        vault.upsert(entity_type="note", data={"title": "Note 1"})

        # List all
        all_entities = vault.list_entities()
        assert len(all_entities) >= 3

        # Filter by type
        tasks = vault.list_entities(entity_type="task")
        assert len(tasks) >= 2

        notes = vault.list_entities(entity_type="note")
        assert len(notes) >= 1


def test_vault_atomic_write():
    """Test atomic write helper."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)

        test_file = Path(tmpdir) / "test" / "atomic.txt"
        content = "Test atomic write content"

        # Write atomically
        vault.atomic_write(test_file, content, create_dirs=True)

        # Verify
        assert test_file.exists()
        assert test_file.read_text() == content


def test_vault_file_locking_concurrent_writes():
    """Test file locking prevents concurrent write conflicts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=True)
        vault = Vault(config)

        # Create initial entity
        entity = vault.upsert(
            entity_type="task",
            data={"title": "Original", "status": "todo"},
        )
        entity_id = entity.id

        # Track results from threads
        results = []
        errors = []

        def update_entity(new_title: str, delay: float = 0) -> None:
            """Update entity in thread."""
            try:
                if delay:
                    time.sleep(delay)

                updated = vault.upsert(
                    entity_type="task",
                    data={"id": entity_id, "title": new_title, "status": "doing"},
                )
                results.append(updated.metadata["title"])
            except Exception as exc:
                errors.append(str(exc))

        # Launch concurrent updates
        thread1 = threading.Thread(target=update_entity, args=("Thread 1",))
        thread2 = threading.Thread(target=update_entity, args=("Thread 2", 0.01))

        thread1.start()
        thread2.start()

        thread1.join(timeout=5)
        thread2.join(timeout=5)

        # Both should complete successfully (locks prevent conflicts)
        assert len(results) == 2
        assert len(errors) == 0

        # Final state should be one of the two updates
        final = vault.get(entity_id)
        assert final.metadata["title"] in ["Thread 1", "Thread 2"]


def test_vault_no_file_locks():
    """Test vault works with file locking disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=False)
        vault = Vault(config)

        # Should work normally
        entity = vault.upsert(
            entity_type="task",
            data={"title": "Test Task", "status": "todo"},
        )

        retrieved = vault.get(entity.id)
        assert retrieved.id == entity.id


def test_vault_round_trip():
    """Test round-trip: create, read, update, read again."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)

        # Create
        original = vault.upsert(
            entity_type="task",
            data={"title": "Original", "status": "todo", "priority": "high"},
            content="Original content",
        )

        # Read
        retrieved1 = vault.get(original.id)
        assert retrieved1.metadata["title"] == "Original"
        assert retrieved1.metadata["status"] == "todo"
        assert retrieved1.content == "Original content"

        # Update
        vault.upsert(
            entity_type="task",
            data={"id": original.id, "title": "Updated", "status": "done"},
            content="Updated content",
        )

        # Read again
        retrieved2 = vault.get(original.id)
        assert retrieved2.metadata["title"] == "Updated"
        assert retrieved2.metadata["status"] == "done"
        assert retrieved2.content == "Updated content"
        # Priority should still be there (partial update)
        assert retrieved2.metadata["priority"] == "high"
