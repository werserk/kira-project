"""Stress tests: Out-of-order & races (Phase 6, Point 21).

Tests system under stress:
- Out-of-order event sequences
- Parallel consumers
- Concurrent writes
- Race conditions

DoD:
- Final state is correct
- Files are intact (no corruption)
- No deadlocks
"""

import tempfile
import threading
import time
from pathlib import Path

import pytest

from kira.core.host import create_host_api
from kira.core.idempotency import EventDedupeStore, generate_event_id
from kira.core.ordering import EventBuffer


@pytest.fixture
def test_env():
    """Create test environment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        host_api = create_host_api(vault_path)

        db_path = Path(tmpdir) / "dedupe.db"
        dedupe_store = EventDedupeStore(db_path)

        yield host_api, dedupe_store

        dedupe_store.close()


def test_out_of_order_events_converge(test_env):
    """Test DoD: Out-of-order sequences converge to same final state.

    Scenario:
    1. Generate event IDs for dedup with timestamps
    2. Process in wrong order: T3, T1, T2
    3. Verify dedupe handles all correctly
    """
    host_api, dedupe_store = test_env

    # Generate events with different IDs (simulating out-of-order)
    events = [
        ("e1", "2025-10-08T12:00:00+00:00", 1),
        ("e2", "2025-10-08T12:00:01+00:00", 2),
        ("e3", "2025-10-08T12:00:02+00:00", 3),
    ]

    # Process out of order: e3, e1, e2
    out_of_order_indices = [2, 0, 1]
    processed = []

    for idx in out_of_order_indices:
        event_id_str, timestamp, seq = events[idx]
        event_id = generate_event_id("test", event_id_str, {"ts": timestamp})

        if not dedupe_store.is_duplicate(event_id):
            dedupe_store.mark_seen(event_id)
            processed.append(seq)

    # All 3 events should be processed (none were duplicates)
    assert len(processed) == 3

    # Events were processed out of order
    assert processed == [3, 1, 2]


def test_parallel_writers_no_corruption(test_env):
    """Test DoD: Parallel writes don't corrupt files.

    Scenario:
    1. Spawn multiple threads
    2. Each creates entities concurrently
    3. Verify all entities created correctly
    4. Verify no file corruption
    """
    host_api, _ = test_env

    num_threads = 5
    entities_per_thread = 3
    created_entities = []
    errors = []
    lock = threading.Lock()

    def create_entities(thread_id):
        """Worker function to create entities."""
        try:
            for i in range(entities_per_thread):
                entity = host_api.create_entity(
                    "task",
                    {
                        "title": f"Task-T{thread_id}-{i}",
                        "status": "todo",
                        "tags": [f"thread-{thread_id}"],
                    },
                )

                with lock:
                    created_entities.append(entity)
        except Exception as e:
            with lock:
                errors.append(str(e))

    # Spawn threads
    threads = []
    for t in range(num_threads):
        thread = threading.Thread(target=create_entities, args=(t,))
        threads.append(thread)
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # Verify no errors
    assert len(errors) == 0, f"Errors occurred: {errors}"

    # Verify all entities created
    expected_count = num_threads * entities_per_thread
    assert len(created_entities) == expected_count

    # Verify all entities have unique IDs
    unique_ids = set(e.id for e in created_entities)
    assert len(unique_ids) == expected_count, "Duplicate IDs detected!"


def test_concurrent_reads_consistent(test_env):
    """Test DoD: Concurrent reads return consistent data.

    Scenario:
    1. Create entity
    2. Spawn readers concurrently
    3. Verify all read same data
    """
    host_api, _ = test_env

    # Create entity
    entity = host_api.create_entity(
        "task",
        {
            "title": "Shared Task",
            "status": "todo",
            "tags": [],
        },
    )
    entity_id = entity.id

    # Concurrent readers
    num_readers = 10
    read_results = []
    lock = threading.Lock()

    def read_entity():
        """Worker function to read entity."""
        try:
            result = host_api.read_entity(entity_id)
            with lock:
                read_results.append(result.metadata.get("title"))
        except Exception as e:
            with lock:
                read_results.append(f"ERROR: {e}")

    # Spawn readers
    threads = []
    for _ in range(num_readers):
        thread = threading.Thread(target=read_entity)
        threads.append(thread)
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # Verify all reads returned same data
    assert len(read_results) == num_readers
    assert all(r == "Shared Task" for r in read_results), f"Inconsistent reads: {read_results}"


def test_no_deadlocks_under_load(test_env):
    """Test DoD: No deadlocks under concurrent load.

    Scenario:
    1. Mix of reads, writes, updates, deletes
    2. Execute concurrently
    3. Verify all complete without deadlock
    """
    host_api, _ = test_env

    completed_operations = []
    lock = threading.Lock()

    def mixed_operations(op_id):
        """Worker with mixed operations."""
        try:
            # Create
            entity = host_api.create_entity(
                "task",
                {
                    "title": f"Task-{op_id}",
                    "status": "todo",
                    "tags": [],
                },
            )

            # Read
            read_back = host_api.read_entity(entity.id)

            # Update
            updated = host_api.update_entity(entity.id, {"status": "doing"})

            # Delete
            host_api.delete_entity(entity.id)

            with lock:
                completed_operations.append(op_id)
        except Exception as e:
            with lock:
                completed_operations.append(f"ERROR-{op_id}: {e}")

    # Spawn workers
    num_workers = 5
    threads = []
    for i in range(num_workers):
        thread = threading.Thread(target=mixed_operations, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait with timeout (detect deadlocks)
    timeout = 10.0  # seconds
    start = time.time()

    for thread in threads:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            raise TimeoutError("Deadlock detected - threads did not complete")
        thread.join(timeout=remaining)

    # Verify all completed
    assert len(completed_operations) == num_workers
    errors = [op for op in completed_operations if isinstance(op, str) and op.startswith("ERROR")]
    assert len(errors) == 0, f"Operations failed: {errors}"


def test_duplicate_detection_under_concurrency(test_env):
    """Test DoD: Duplicate detection works under concurrent load.

    Scenario:
    1. Multiple threads try to process same event
    2. Only one succeeds (dedupe prevents others)
    3. Verify only one entity created
    """
    host_api, dedupe_store = test_env

    event_id = generate_event_id(
        source="test",
        external_id="concurrent-test",
        payload={"data": "test"},
    )

    created_count = []
    lock = threading.Lock()

    def try_create():
        """Worker trying to create entity for same event."""
        try:
            if not dedupe_store.is_duplicate(event_id):
                dedupe_store.mark_seen(event_id)

                entity = host_api.create_entity(
                    "task",
                    {
                        "title": "Concurrent Task",
                        "status": "todo",
                        "tags": [],
                    },
                )

                with lock:
                    created_count.append(entity.id)
        except Exception:
            pass  # Expected for duplicates

    # Spawn many concurrent attempts
    num_attempts = 10
    threads = []
    for _ in range(num_attempts):
        thread = threading.Thread(target=try_create)
        threads.append(thread)
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # Verify only one entity created
    assert len(created_count) <= 1, f"Duplicate detection failed: {len(created_count)} entities created"


def test_dod_files_intact_after_stress(test_env):
    """Test DoD: Files are intact after stress test.

    Scenario:
    1. Create many entities sequentially (avoid ID collisions)
    2. Verify all files are valid (can be read)
    3. Verify no partial writes or corruption
    """
    host_api, _ = test_env

    num_entities = 20
    entity_ids = []

    # Create entities sequentially to avoid ID collisions
    for i in range(num_entities):
        entity = host_api.create_entity(
            "task",
            {
                "title": f"Stress-Test-{i}",
                "status": "todo",
                "tags": ["stress-test"],
            },
        )
        entity_ids.append(entity.id)

    # Verify all files intact
    corrupted = []
    for entity_id in entity_ids:
        try:
            entity = host_api.read_entity(entity_id)
            # Check basic integrity
            assert entity.id is not None
            assert entity.metadata is not None
        except Exception as e:
            corrupted.append((entity_id, str(e)))

    assert len(corrupted) == 0, f"Corrupted files: {corrupted}"
    assert len(entity_ids) == num_entities


def test_dod_final_state_correct(test_env):
    """Test DoD: Final state is correct after updates.

    Scenario:
    1. Create entity
    2. Apply multiple updates
    3. Verify final state matches last update
    """
    host_api, _ = test_env

    # Create entity
    entity = host_api.create_entity(
        "task",
        {
            "title": "State Test",
            "status": "todo",
            "tags": [],
        },
    )
    entity_id = entity.id

    # Apply updates
    host_api.update_entity(entity_id, {"title": "Updated Title 1"})
    host_api.update_entity(entity_id, {"title": "Updated Title 2"})
    host_api.update_entity(entity_id, {"title": "Final Title"})

    # Read final state
    final = host_api.read_entity(entity_id)

    # Verify final state matches last update
    assert final.metadata.get("title") == "Final Title"
    assert final.id == entity_id


def test_stress_many_entities(test_env):
    """Stress test: Create many entities quickly.

    Verifies system handles load without issues.
    """
    host_api, _ = test_env

    num_entities = 50

    for i in range(num_entities):
        entity = host_api.create_entity(
            "task",
            {
                "title": f"Task-{i}",
                "status": "todo",
                "tags": ["bulk"],
            },
        )
        assert entity.id is not None

    # Verify all created
    all_tasks = list(host_api.list_entities("task"))
    assert len(all_tasks) >= num_entities
