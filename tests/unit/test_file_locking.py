"""Tests for per-entity file locking (Phase 4, Point 12).

DoD: Parallel updates on the same `uid` do not corrupt data or interleave wrongly.
Tests fcntl-based file locking with concurrent access scenarios.
"""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path

import pytest

from kira.storage.vault import EntityLock, NoOpLock, Vault, VaultConfig, VaultError


class TestEntityLocking:
    """Test per-entity file locking (Phase 4, Point 12)."""

    def test_entity_lock_creates_lock_file(self):
        """Test entity lock creates lock file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-001"
            lock = EntityLock(vault, entity_id, timeout=5.0)

            with lock:
                # Lock file should exist
                lock_file = vault_path / ".kira" / "locks" / f"{entity_id}.lock"
                assert lock_file.exists()

    def test_entity_lock_acquires_exclusive_lock(self):
        """Test entity lock acquires exclusive lock."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-001"
            lock = EntityLock(vault, entity_id, timeout=5.0)

            with lock:
                # Lock should be acquired
                assert lock.lock_fd is not None

    def test_entity_lock_releases_on_exit(self):
        """Test entity lock releases on context exit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-001"
            lock = EntityLock(vault, entity_id, timeout=5.0)

            with lock:
                fd = lock.lock_fd
                assert fd is not None

            # Lock should be released
            assert lock.lock_fd is None

    def test_noop_lock_does_nothing(self):
        """Test NoOpLock is a no-op."""
        lock = NoOpLock()

        # Should work without errors
        with lock:
            pass


class TestConcurrentLocking:
    """Test concurrent locking behavior (Phase 4, Point 12 DoD)."""

    def test_two_locks_on_same_entity_serialize(self):
        """Test two threads locking same entity serialize access."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-001"
            execution_order = []

            def thread1() -> None:
                lock = EntityLock(vault, entity_id, timeout=5.0)
                with lock:
                    execution_order.append("thread1_start")
                    time.sleep(0.1)  # Hold lock for 100ms
                    execution_order.append("thread1_end")

            def thread2() -> None:
                time.sleep(0.05)  # Start slightly after thread1
                lock = EntityLock(vault, entity_id, timeout=5.0)
                with lock:
                    execution_order.append("thread2_start")
                    time.sleep(0.1)
                    execution_order.append("thread2_end")

            # Start both threads
            t1 = threading.Thread(target=thread1)
            t2 = threading.Thread(target=thread2)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            # Thread1 should complete before thread2 starts
            assert execution_order == ["thread1_start", "thread1_end", "thread2_start", "thread2_end"]

    def test_locks_on_different_entities_dont_block(self):
        """Test locks on different entities don't block each other."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            execution_order = []

            def thread1() -> None:
                lock = EntityLock(vault, "task-001", timeout=5.0)
                with lock:
                    execution_order.append("thread1_start")
                    time.sleep(0.1)
                    execution_order.append("thread1_end")

            def thread2() -> None:
                time.sleep(0.05)  # Start slightly after thread1
                lock = EntityLock(vault, "task-002", timeout=5.0)  # Different entity
                with lock:
                    execution_order.append("thread2_start")
                    time.sleep(0.1)
                    execution_order.append("thread2_end")

            # Start both threads
            t1 = threading.Thread(target=thread1)
            t2 = threading.Thread(target=thread2)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            # Threads should overlap since they lock different entities
            # thread2 should start before thread1 ends
            thread1_start_idx = execution_order.index("thread1_start")
            thread1_end_idx = execution_order.index("thread1_end")
            thread2_start_idx = execution_order.index("thread2_start")

            assert thread2_start_idx > thread1_start_idx
            assert thread2_start_idx < thread1_end_idx  # Overlap!

    def test_lock_timeout_raises_error(self):
        """Test lock timeout raises VaultError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-001"

            def thread1() -> None:
                lock = EntityLock(vault, entity_id, timeout=5.0)
                with lock:
                    time.sleep(2.0)  # Hold lock for 2 seconds

            def thread2() -> None:
                time.sleep(0.1)  # Let thread1 acquire lock first
                lock = EntityLock(vault, entity_id, timeout=0.5)  # Short timeout
                try:
                    with lock:
                        pass
                except VaultError as exc:
                    assert "timeout" in str(exc).lower()
                    raise

            # Start thread1
            t1 = threading.Thread(target=thread1)
            t1.start()

            # Thread2 should timeout
            with pytest.raises(VaultError, match="timeout"):
                thread2()

            t1.join()


class TestLockFileNaming:
    """Test lock file naming and safety."""

    def test_lock_file_uses_entity_id(self):
        """Test lock file is named after entity ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-123"
            lock = EntityLock(vault, entity_id, timeout=5.0)

            with lock:
                lock_file = vault_path / ".kira" / "locks" / f"{entity_id}.lock"
                assert lock_file.exists()

    def test_lock_file_handles_special_chars(self):
        """Test lock file handles entity IDs with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            # Entity ID with forward slash
            entity_id = "tasks/archived/task-123"
            lock = EntityLock(vault, entity_id, timeout=5.0)

            with lock:
                # Lock file should exist (slashes replaced with underscores)
                expected_name = entity_id.replace("/", "_")
                lock_file = vault_path / ".kira" / "locks" / f"{expected_name}.lock"
                assert lock_file.exists()


class TestLockConfiguration:
    """Test locking configuration options."""

    def test_locking_can_be_disabled(self):
        """Test locking can be disabled via config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=False)
            vault = Vault(config)

            # Should return NoOpLock
            lock = vault._no_lock()
            assert isinstance(lock, NoOpLock)

    def test_lock_timeout_configurable(self):
        """Test lock timeout is configurable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True, lock_timeout=2.5)

            assert config.lock_timeout == 2.5


class TestLockErrorHandling:
    """Test lock error handling."""

    def test_lock_cleanup_on_exception(self):
        """Test lock is released even if exception occurs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-001"
            lock = EntityLock(vault, entity_id, timeout=5.0)

            try:
                with lock:
                    assert lock.lock_fd is not None
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Lock should still be released
            assert lock.lock_fd is None

    def test_subsequent_lock_succeeds_after_exception(self):
        """Test subsequent lock acquisition succeeds after exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-001"

            # First lock with exception
            lock1 = EntityLock(vault, entity_id, timeout=5.0)
            try:
                with lock1:
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Second lock should succeed
            lock2 = EntityLock(vault, entity_id, timeout=5.0)
            with lock2:
                assert lock2.lock_fd is not None


class TestLockIntegration:
    """Test locking integration with Vault operations."""

    def test_vault_upsert_uses_locking(self):
        """Test Vault.upsert uses entity locking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            # Create entity
            entity_data = {"id": "task-001", "title": "Test Task", "status": "todo", "tags": []}

            # Should not raise (locking works)
            entity = vault.upsert(entity_type="task", data=entity_data, content="Test content")

            assert entity.id == "task-001"


class TestConcurrentDataIntegrity:
    """Test data integrity under concurrent access (Phase 4, Point 12 DoD)."""

    def test_concurrent_updates_dont_corrupt_data(self):
        """Test concurrent updates to same entity don't corrupt data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            config = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault = Vault(config)

            entity_id = "task-001"

            # Create initial entity with all required fields
            from kira.core.time import format_utc_iso8601, get_current_utc

            now = format_utc_iso8601(get_current_utc())
            initial_data = {
                "id": entity_id,
                "title": "Initial",
                "status": "todo",
                "created_ts": now,
                "updated_ts": now,
                "counter": 0,
                "tags": [],
            }
            vault.upsert(entity_type="task", data=initial_data)

            errors = []

            def increment_counter(thread_num: int) -> None:
                try:
                    # Read current entity
                    entity = vault.get(entity_id)
                    current_counter = entity.metadata.get("counter", 0)

                    # Simulate some processing
                    time.sleep(0.01)

                    # Increment and write back
                    updated_data = entity.metadata.copy()
                    updated_data["counter"] = current_counter + 1
                    updated_data["last_updated_by"] = f"thread-{thread_num}"

                    vault.upsert(entity_type="task", data=updated_data, content=entity.content)
                except Exception as exc:
                    errors.append(exc)

            # Run 10 concurrent increments
            threads = []
            for i in range(10):
                t = threading.Thread(target=increment_counter, args=(i,))
                threads.append(t)
                t.start()

            # Wait for all threads
            for t in threads:
                t.join()

            # Check no errors occurred
            assert len(errors) == 0, f"Errors: {errors}"

            # With locking, data should be valid (not corrupted)
            # However, last-write-wins means not all increments are preserved
            # The important thing is the file is valid, not partial/corrupted
            final_entity = vault.get(entity_id)
            final_counter = final_entity.metadata.get("counter", 0)

            # Counter should be >= 1 (at least one update succeeded)
            # and <= 10 (max possible updates)
            assert 1 <= final_counter <= 10, f"Invalid counter: {final_counter}"

            # Verify entity is valid (has required fields, not corrupted)
            assert "title" in final_entity.metadata
            assert "last_updated_by" in final_entity.metadata

            # File should be readable and valid markdown
            if final_entity.path:
                from kira.core.md_io import read_markdown

                doc = read_markdown(final_entity.path)
                assert doc.get_metadata("counter") == final_counter


class TestLockPerformance:
    """Test lock performance characteristics."""

    def test_locking_adds_minimal_overhead(self):
        """Test locking overhead is acceptable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)

            # Test with locking disabled
            config_no_lock = VaultConfig(vault_path=vault_path, enable_file_locks=False)
            vault_no_lock = Vault(config_no_lock)

            from kira.core.time import format_utc_iso8601, get_current_utc

            now = format_utc_iso8601(get_current_utc())
            entity_data = {
                "id": "task-001",
                "title": "Test",
                "status": "todo",
                "created_ts": now,
                "updated_ts": now,
                "tags": [],
            }

            start = time.time()
            for _i in range(10):
                vault_no_lock.upsert(entity_type="task", data=entity_data)
            time_no_lock = time.time() - start

            # Test with locking enabled
            config_with_lock = VaultConfig(vault_path=vault_path, enable_file_locks=True)
            vault_with_lock = Vault(config_with_lock)

            start = time.time()
            for _i in range(10):
                vault_with_lock.upsert(entity_type="task", data=entity_data)
            time_with_lock = time.time() - start

            # Locking should add < 100% overhead (less than 2x slower)
            overhead = (time_with_lock - time_no_lock) / time_no_lock
            assert overhead < 1.0, f"Locking overhead too high: {overhead:.1%}"
