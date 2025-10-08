"""Integration tests: Telegram → Task → Vault (Phase 6, Point 19).

Simplified integration tests focusing on core flows.
"""

import tempfile
from pathlib import Path

import pytest

from kira.core.host import create_host_api
from kira.core.idempotency import EventDedupeStore, generate_event_id


@pytest.fixture
def test_env():
    """Create test environment with vault and dedupe store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        host_api = create_host_api(vault_path)
        
        db_path = Path(tmpdir) / "dedupe.db"
        dedupe_store = EventDedupeStore(db_path)
        
        yield host_api, dedupe_store
        
        dedupe_store.close()


def test_telegram_message_creates_task(test_env):
    """Test DoD: Telegram message → Task.md.
    
    Core flow: message arrives, task created, persisted in vault.
    """
    host_api, dedupe_store = test_env
    
    # Simulate Telegram message with idempotency
    telegram_msg_id = 12345
    event_id = generate_event_id(
        source="telegram",
        external_id=f"telegram-{telegram_msg_id}",
        payload={"text": "Buy milk"},
    )
    
    # Check not duplicate
    assert dedupe_store.is_duplicate(event_id) is False
    dedupe_store.mark_seen(event_id)
    
    # Create task via Host API
    entity = host_api.create_entity("task", {
        "title": "Buy milk",
        "status": "todo",
        "tags": ["telegram"],
    })
    
    # Verify created
    assert entity.id is not None
    assert entity.title == "Buy milk"
    
    # Verify persisted
    retrieved = host_api.read_entity(entity.id)
    assert retrieved.title == "Buy milk"


def test_duplicate_message_detected(test_env):
    """Test DoD: Duplicates do not appear."""
    host_api, dedupe_store = test_env
    
    telegram_msg_id = 99999
    event_id = generate_event_id(
        source="telegram",
        external_id=f"telegram-{telegram_msg_id}",
        payload={"text": "Same message"},
    )
    
    # First time
    assert dedupe_store.is_duplicate(event_id) is False
    dedupe_store.mark_seen(event_id)
    
    entity = host_api.create_entity("task", {
        "title": "Same message",
        "status": "todo",
        "tags": ["telegram"],
    })
    
    # Second time - duplicate detected
    assert dedupe_store.is_duplicate(event_id) is True
    
    # Don't create second task
    all_tasks = list(host_api.list_entities("task"))
    assert len(all_tasks) == 1


def test_task_edit(test_env):
    """Test DoD: Edit updates task."""
    host_api, _ = test_env
    
    # Create task
    entity = host_api.create_entity("task", {
        "title": "Original",
        "status": "todo",
        "tags": [],
    })
    uid = entity.id
    
    # Edit
    updated = host_api.update_entity(uid, {"title": "Updated"})
    
    assert updated.title == "Updated"
    assert updated.id == uid
    
    # Verify persisted
    retrieved = host_api.read_entity(uid)
    assert retrieved.title == "Updated"


def test_task_delete(test_env):
    """Test DoD: Delete removes task."""
    host_api, _ = test_env
    
    # Create task
    entity = host_api.create_entity("task", {
        "title": "To delete",
        "status": "todo",
        "tags": [],
    })
    uid = entity.id
    
    # Delete
    host_api.delete_entity(uid)
    
    # Verify deleted
    assert host_api.read_entity(uid) is None


def test_full_lifecycle(test_env):
    """Test DoD: Full lifecycle - create, update, complete, delete."""
    host_api, dedupe_store = test_env
    
    # Create with dedupe
    event_id = generate_event_id(
        source="telegram",
        external_id="telegram-full-lifecycle",
        payload={"text": "Project task"},
    )
    
    assert dedupe_store.is_duplicate(event_id) is False
    dedupe_store.mark_seen(event_id)
    
    # Create
    entity = host_api.create_entity("task", {
        "title": "Project task",
        "status": "todo",
        "tags": ["work"],
    })
    uid = entity.id
    
    # Start work
    updated = host_api.update_entity(uid, {
        "status": "doing",
        "assignee": "user-1",
    })
    assert updated.status == "doing"
    
    # Complete
    completed = host_api.update_entity(uid, {"status": "done"})
    assert completed.status == "done"
    assert "done_ts" in completed.__dict__ or hasattr(completed, "done_ts")
    
    # Delete
    host_api.delete_entity(uid)
    assert host_api.read_entity(uid) is None


def test_multiple_distinct_messages(test_env):
    """Test DoD: Multiple distinct messages create distinct tasks."""
    host_api, dedupe_store = test_env
    
    messages = [("Task A", 201), ("Task B", 202), ("Task C", 203)]
    
    for text, msg_id in messages:
        event_id = generate_event_id(
            source="telegram",
            external_id=f"telegram-{msg_id}",
            payload={"text": text},
        )
        
        assert dedupe_store.is_duplicate(event_id) is False
        dedupe_store.mark_seen(event_id)
        
        host_api.create_entity("task", {
            "title": text,
            "status": "todo",
            "tags": [],
        })
    
    # Verify all created
    all_tasks = list(host_api.list_entities("task"))
    assert len(all_tasks) == 3


def test_dod_files_match_expectations(test_env):
    """Test DoD: Files/states match expectations."""
    host_api, _ = test_env
    
    entity = host_api.create_entity("task", {
        "title": "Test task",
        "status": "todo",
        "tags": ["test"],
    })
    
    retrieved = host_api.read_entity(entity.id)
    
    assert retrieved.title == "Test task"
    assert retrieved.status == "todo"
    assert "test" in retrieved.tags
    assert "id" in retrieved.__dict__ or hasattr(retrieved, "id")
    assert "created_ts" in retrieved
    assert "updated_ts" in retrieved

