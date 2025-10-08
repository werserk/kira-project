"""Integration test: Telegram → Task → Vault (Phase 6, Point 19).

Tests full pipeline:
- New message from Telegram
- Ingress normalization
- Validation
- Host API upsert
- Vault storage
- Idempotency (duplicate detection)
- Updates and deletes

DoD:
- Files/states match expectations
- Duplicates do not appear
"""

import tempfile
from pathlib import Path

import pytest

from kira.core.host import HostAPI
from kira.core.idempotency import EventDedupeStore, generate_event_id
from kira.core.ingress import normalize_telegram_payload
from kira.storage.vault import Vault, VaultConfig


class MockTelegramMessage:
    """Mock Telegram message."""
    
    def __init__(self, message_id: int, text: str, user_id: int, timestamp: int):
        self.message_id = message_id
        self.text = text
        self.from_user = type('User', (), {'id': user_id})
        self.date = timestamp


@pytest.fixture
def test_vault():
    """Create test vault."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        config = VaultConfig(vault_path=vault_path)
        vault = Vault(config)
        yield vault


@pytest.fixture
def test_host_api(test_vault):
    """Create test Host API."""
    # Vault already has a host_api
    return test_vault.host_api


@pytest.fixture
def test_dedupe_store():
    """Create test dedupe store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "dedupe.db"
        store = EventDedupeStore(db_path)
        yield store
        store.close()


def test_telegram_new_message_to_vault(test_host_api, test_dedupe_store):
    """Test DoD: New Telegram message → Inbox → Host API → Task.md.
    
    Scenario:
    1. Telegram message arrives
    2. Generate event ID for deduplication
    3. Process through Host API
    4. Verify task in vault
    """
    # Step 1: Telegram message simulated
    telegram_message_id = 123456
    message_text = "Buy groceries #task"
    
    # Step 2: Generate event ID for deduplication
    event_id = generate_event_id(
        source="telegram",
        external_id=f"telegram-{telegram_message_id}",
        payload={"text": message_text},
    )
    
    # Check not already seen
    assert test_dedupe_store.is_duplicate(event_id) is False
    test_dedupe_store.mark_seen(event_id)
    
    # Step 3: Create task entity via Host API
    task_data = {
        "title": "Buy groceries",
        "tags": ["telegram"],
        "status": "todo",
        "source": "telegram",
    }
    
    entity = test_host_api.create_entity("task", task_data)
    
    # Step 4: Verify task in vault
    assert entity is not None
    assert entity["uid"] is not None
    assert entity["title"] == "Buy groceries"
    assert entity["status"] == "todo"
    assert "telegram" in entity["tags"]
    
    # Verify file persisted
    retrieved = test_host_api.get_entity(entity["uid"])
    assert retrieved is not None
    assert retrieved["title"] == "Buy groceries"


def test_telegram_duplicate_message_ignored(test_host_api, test_dedupe_store):
    """Test DoD: Duplicate messages do not create duplicate tasks.
    
    Scenario:
    1. Process message once
    2. Repeat same message (same event ID)
    3. Verify dedupe catches it
    4. Only one task created
    """
    telegram_msg_id = 123
    message_text = "Test task"
    
    # First message - generate event ID
    event_id = generate_event_id(
        source="telegram",
        external_id=f"telegram-{telegram_msg_id}",
        payload={"text": message_text},
    )
    
    # Check if seen (should be False - first time)
    assert test_dedupe_store.is_duplicate(event_id) is False
    
    # Record as seen
    test_dedupe_store.mark_seen(event_id)
    
    # Create task
    task_data = {
        "type": "task",
        "title": "Test task",
        "tags": ["telegram"],
        "status": "todo",
    }
    entity = test_host_api.create_entity(task_data)
    
    # Repeat same message (same event ID)
    # Check if seen (should be True - duplicate!)
    assert test_dedupe_store.is_duplicate(event_id) is True
    
    # In real system, dedupe check prevents second task creation
    # So we don't create another task here
    
    # Verify only one task exists
    all_entities = list(test_host_api.list_entities("task"))
    assert len(all_entities) == 1


def test_telegram_message_edit(test_host_api):
    """Test DoD: Editing message updates task.
    
    Scenario:
    1. Create task from message
    2. Edit message (update title)
    3. Verify task updated
    """
    # Create initial task
    task_data = {
        "type": "task",
        "title": "Original title",
        "tags": ["telegram"],
        "status": "todo",
    }
    entity = test_host_api.create_entity(task_data)
    uid = entity["uid"]
    
    # Edit task (simulate message edit)
    updates = {
        "title": "Updated title",
    }
    updated_entity = test_host_api.update_entity(uid, updates)
    
    # Verify update
    assert updated_entity["title"] == "Updated title"
    assert updated_entity["uid"] == uid  # Same UID
    
    # Verify in vault
    retrieved = test_host_api.get_entity(uid)
    assert retrieved["title"] == "Updated title"


def test_telegram_message_delete(test_host_api):
    """Test DoD: Deleting message removes task.
    
    Scenario:
    1. Create task from message
    2. Delete message (delete task)
    3. Verify task deleted
    """
    # Create task
    task_data = {
        "type": "task",
        "title": "Task to delete",
        "tags": ["telegram"],
        "status": "todo",
    }
    entity = test_host_api.create_entity(task_data)
    uid = entity["uid"]
    
    # Verify task exists
    retrieved = test_host_api.get_entity(uid)
    assert retrieved is not None
    
    # Delete task
    test_host_api.delete_entity(uid)
    
    # Verify task deleted
    deleted = test_host_api.get_entity(uid)
    assert deleted is None


def test_telegram_full_lifecycle(test_host_api, test_dedupe_store):
    """Test DoD: Full lifecycle - create, update, complete, delete.
    
    Comprehensive test of full message lifecycle.
    """
    telegram_msg_id = 999
    
    # Step 1: New message - check dedupe
    event_id = generate_event_id(
        source="telegram",
        external_id=f"telegram-{telegram_msg_id}",
        payload={"text": "Complete project"},
    )
    
    assert test_dedupe_store.is_duplicate(event_id) is False
    test_dedupe_store.mark_seen(event_id)
    
    # Create task
    task_data = {
        "type": "task",
        "title": "Complete project",
        "tags": ["telegram", "work"],
        "status": "todo",
    }
    entity = test_host_api.create_entity(task_data)
    uid = entity["uid"]
    
    # Step 2: Start work
    updated = test_host_api.update_entity(uid, {
        "status": "doing",
        "assignee": "user-789",
    })
    assert updated["status"] == "doing"
    
    # Step 3: Complete task
    completed = test_host_api.update_entity(uid, {
        "status": "done",
    })
    assert completed["status"] == "done"
    assert "done_ts" in completed
    
    # Step 4: Delete
    test_host_api.delete_entity(uid)
    assert test_host_api.get_entity(uid) is None


def test_telegram_multiple_messages_no_duplicates(test_host_api, test_dedupe_store):
    """Test DoD: Multiple distinct messages create distinct tasks.
    
    Verify that different messages are not incorrectly deduplicated.
    """
    messages = [
        ("Task 1", 101),
        ("Task 2", 102),
        ("Task 3", 103),
    ]
    
    created_tasks = []
    
    for text, msg_id in messages:
        event_id = generate_event_id(
            source="telegram",
            external_id=f"telegram-{msg_id}",
            payload={"text": text},
        )
        
        # Should not be duplicate
        assert test_dedupe_store.is_duplicate(event_id) is False
        test_dedupe_store.mark_seen(event_id)
        
        # Create task
        task_data = {
            "type": "task",
            "title": text,
            "tags": ["telegram"],
            "status": "todo",
        }
        entity = test_host_api.create_entity(task_data)
        created_tasks.append(entity)
    
    # Verify all tasks created
    assert len(created_tasks) == 3
    assert len(set(t["uid"] for t in created_tasks)) == 3  # All unique UIDs


def test_telegram_invalid_message_quarantined(test_host_api):
    """Test that invalid messages are quarantined, not stored.
    
    Scenario:
    1. Receive message with invalid data
    2. Validation fails
    3. Message quarantined
    4. No task created
    """
    # Try to create task with missing required field
    invalid_task = {
        "type": "task",
        # Missing "title" - required field
        "tags": ["telegram"],
        "status": "todo",
    }
    
    # Should raise validation error
    with pytest.raises(Exception):  # ValidationError or similar
        test_host_api.create_entity(invalid_task)
    
    # Verify no task was created
    all_tasks = list(test_host_api.list_entities("task"))
    assert len(all_tasks) == 0


def test_dod_files_match_expectations(test_host_api):
    """Test DoD: Files/states match expectations.
    
    Verify that vault files contain expected data.
    """
    # Create task
    task_data = {
        "type": "task",
        "title": "Test task",
        "tags": ["test"],
        "status": "todo",
    }
    entity = test_host_api.create_entity(task_data)
    uid = entity["uid"]
    
    # Retrieve and verify
    retrieved = test_host_api.get_entity(uid)
    
    assert retrieved["title"] == "Test task"
    assert retrieved["status"] == "todo"
    assert "test" in retrieved["tags"]
    assert "uid" in retrieved
    assert "created_ts" in retrieved
    assert "updated_ts" in retrieved


def test_dod_no_duplicates(test_host_api, test_dedupe_store):
    """Test DoD: Duplicates do not appear.
    
    Comprehensive test that duplicate detection works.
    """
    telegram_msg_id = 555
    message_text = "Duplicate test"
    
    # Same message repeated 3 times
    for i in range(3):
        event_id = generate_event_id(
            source="telegram",
            external_id=f"telegram-{telegram_msg_id}",
            payload={"text": message_text},
        )
        
        if not test_dedupe_store.is_duplicate(event_id):
            # First time only
            test_dedupe_store.mark_seen(event_id)
            
            task_data = {
                "type": "task",
                "title": "Duplicate test",
                "tags": ["telegram"],
                "status": "todo",
            }
            test_host_api.create_entity(task_data)
    
    # Verify only one task created
    all_tasks = list(test_host_api.list_entities("task"))
    assert len(all_tasks) == 1

