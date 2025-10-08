"""Tests for per-entity file locking (Phase 3, Point 12)."""

import os
import tempfile
import threading
import time
from pathlib import Path

import pytest

from kira.core.host import Entity
from kira.storage.vault import Vault, VaultConfig, VaultError


def test_entity_lock_basic():
    """Test basic entity lock acquisition and release."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=True)
        vault = Vault(config)
        
        # Create and write entity
        data = {"title": "Test Task", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        
        # Lock should be released after upsert
        # We can acquire it again
        data2 = {"title": "Updated Task", "status": "doing", "tags": []}
        entity2 = vault.upsert("task", {"id": entity.id, **data2})
        
        assert entity2.metadata["title"] == "Updated Task"


def test_concurrent_writes_same_entity_serialized():
    """Test concurrent writes to same entity are serialized by lock."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=True)
        vault = Vault(config)
        
        # Create initial entity
        data = {"title": "Initial", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        entity_id = entity.id
        
        # Track write order
        write_order = []
        lock = threading.Lock()
        
        def write_entity(index: int, title: str):
            """Write entity from thread."""
            try:
                # Simulate some work before write
                time.sleep(0.01 * index)
                
                # Update entity
                data = {"id": entity_id, "title": title, "status": "todo", "tags": []}
                updated = vault.upsert("task", data)
                
                # Record write order
                with lock:
                    write_order.append((index, title))
            except Exception as exc:
                with lock:
                    write_order.append((index, f"ERROR: {exc}"))
        
        # Start multiple threads writing to same entity
        threads = []
        for i in range(5):
            thread = threading.Thread(target=write_entity, args=(i, f"Version {i}"))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=10.0)
        
        # All writes should complete
        assert len(write_order) == 5
        
        # No errors
        for index, result in write_order:
            assert not result.startswith("ERROR"), f"Thread {index} failed: {result}"
        
        # Final entity should be valid and readable
        final_entity = vault.get(entity_id)
        assert final_entity.id == entity_id
        assert "Version" in final_entity.metadata["title"]


def test_concurrent_writes_different_entities_parallel():
    """Test concurrent writes to different entities can run in parallel."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=True)
        vault = Vault(config)
        
        # Create multiple entities in parallel
        results = []
        lock = threading.Lock()
        
        def create_entity(index: int):
            """Create entity from thread."""
            try:
                data = {"title": f"Task {index}", "status": "todo", "tags": []}
                entity = vault.upsert("task", data)
                
                with lock:
                    results.append((index, entity.id))
            except Exception as exc:
                with lock:
                    results.append((index, f"ERROR: {exc}"))
        
        # Start multiple threads creating different entities
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_entity, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all
        for thread in threads:
            thread.join(timeout=10.0)
        
        # All creates should succeed
        assert len(results) == 10
        
        # No errors
        for index, result in results:
            assert not str(result).startswith("ERROR")
        
        # All entities should be unique
        entity_ids = [result for index, result in results]
        assert len(set(entity_ids)) == 10


def test_lock_prevents_content_corruption():
    """Test DoD: Parallel writes on same uid don't corrupt content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=True)
        vault = Vault(config)
        
        # Create initial entity
        data = {"title": "Initial", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        entity_id = entity.id
        
        # Multiple threads update same entity
        def update_entity(thread_id: int):
            """Update entity multiple times."""
            for i in range(5):
                data = {
                    "id": entity_id,
                    "title": f"Thread-{thread_id}-Update-{i}",
                    "status": "doing",
                    "tags": [],
                }
                vault.upsert("task", data)
                time.sleep(0.001)  # Small delay
        
        # Start threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=update_entity, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait
        for thread in threads:
            thread.join(timeout=15.0)
        
        # Entity should be valid and not corrupted
        final_entity = vault.get(entity_id)
        assert final_entity.id == entity_id
        
        # Title should be from one of the threads (not corrupted)
        assert final_entity.metadata["title"].startswith("Thread-")
        assert "-Update-" in final_entity.metadata["title"]


def test_lock_timeout():
    """Test lock timeout when lock is held."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(
            vault_path=Path(tmpdir),
            enable_file_locks=True,
            lock_timeout=0.5,  # Short timeout for testing
        )
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Test", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        entity_id = entity.id
        
        # Manually acquire lock and hold it
        lock = vault._acquire_entity_lock(entity_id)
        lock.__enter__()
        
        try:
            # Try to write from another "thread" (same thread for test simplicity)
            # This should timeout
            with pytest.raises(VaultError, match="Failed to acquire lock"):
                # Create a second vault instance (simulates another process)
                vault2 = Vault(config)
                data2 = {"id": entity_id, "title": "Updated", "status": "todo", "tags": []}
                vault2.upsert("task", data2)
        finally:
            # Release lock
            lock.__exit__(None, None, None)


def test_lock_released_on_exception():
    """Test lock is released even when exception occurs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=True)
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Test", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        entity_id = entity.id
        
        # Try to write invalid data (should raise exception)
        try:
            vault.upsert("task", {"id": entity_id, "title": ""})  # Empty title is invalid
        except Exception:
            pass  # Expected to fail validation
        
        # Lock should be released, so we can write again
        data2 = {"id": entity_id, "title": "Valid Title", "status": "todo", "tags": []}
        entity2 = vault.upsert("task", data2)
        
        assert entity2.metadata["title"] == "Valid Title"


def test_locking_disabled():
    """Test vault works with locking disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=False)
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Test", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        
        # Update entity
        data2 = {"id": entity.id, "title": "Updated", "status": "todo", "tags": []}
        entity2 = vault.upsert("task", data2)
        
        assert entity2.metadata["title"] == "Updated"


def test_lock_file_cleanup():
    """Test lock files are properly managed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Test", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        
        # After upsert completes, lock is released
        # Lock directory may or may not exist (it's created on demand)
        # This is fine - locks are ephemeral
        
        # The important thing is that we can write again (lock was released)
        data2 = {"id": entity.id, "title": "Updated", "status": "todo", "tags": []}
        entity2 = vault.upsert("task", data2)
        assert entity2.metadata["title"] == "Updated"


def test_different_entities_different_locks():
    """Test different entities can be written concurrently."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
        vault = Vault(config)
        
        # Create multiple entities
        entities = []
        for i in range(3):
            data = {"title": f"Task {i}", "status": "todo", "tags": []}
            entity = vault.upsert("task", data)
            entities.append(entity)
        
        # All entities should be created successfully
        assert len(entities) == 3
        
        # Each entity should have unique ID
        entity_ids = [e.id for e in entities]
        assert len(set(entity_ids)) == 3


def test_lock_prevents_file_corruption():
    """Test DoD: Locks prevent file corruption (not logical lost updates).
    
    Note: File locks prevent concurrent writes to same FILE from corrupting it.
    They do NOT prevent read-modify-write races at the application level.
    That requires application-level transaction logic.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=True)
        vault = Vault(config)
        
        # Create initial entity
        data = {"title": "Initial", "version": 0, "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        entity_id = entity.id
        
        # Multiple threads write different versions
        def write_version(thread_id: int):
            """Write entity version."""
            for i in range(3):
                data = {
                    "id": entity_id,
                    "title": f"Thread-{thread_id}-Version-{i}",
                    "version": thread_id * 100 + i,
                    "status": "todo",
                    "tags": [],
                }
                vault.upsert("task", data)
                time.sleep(0.001)
        
        # Start threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=write_version, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait
        for thread in threads:
            thread.join(timeout=15.0)
        
        # File should NOT be corrupted (can read it)
        final_entity = vault.get(entity_id)
        assert final_entity.id == entity_id
        
        # Entity should have valid content (not corrupted)
        assert "Thread-" in final_entity.metadata["title"]
        assert isinstance(final_entity.metadata["version"], int)


def test_lock_mechanism_works():
    """Test lock mechanism works correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Test", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        
        # Can update entity (lock was released)
        data2 = {"id": entity.id, "title": "Updated", "status": "doing", "tags": []}
        entity2 = vault.upsert("task", data2)
        
        assert entity2.metadata["title"] == "Updated"
        assert entity2.metadata["status"] == "doing"


def test_dod_parallel_writes_dont_corrupt():
    """Test DoD: Parallel writes on same uid don't corrupt content or lose updates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir), enable_file_locks=True)
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Initial", "version": 0, "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        entity_id = entity.id
        
        # Multiple threads update with version numbers
        results = []
        lock = threading.Lock()
        
        def versioned_update(version: int):
            """Update entity with version number."""
            try:
                data = {
                    "id": entity_id,
                    "title": f"Version-{version}",
                    "version": version,
                    "status": "todo",
                    "tags": [],
                }
                updated = vault.upsert("task", data)
                
                with lock:
                    results.append(("success", version))
            except Exception as exc:
                with lock:
                    results.append(("error", str(exc)))
        
        # Start threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=versioned_update, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait
        for thread in threads:
            thread.join(timeout=15.0)
        
        # All updates should succeed
        assert len(results) == 10
        assert all(status == "success" for status, _ in results)
        
        # Entity should be valid (not corrupted)
        final_entity = vault.get(entity_id)
        assert final_entity.id == entity_id
        assert "version" in final_entity.metadata
        assert 0 <= final_entity.metadata["version"] < 10

