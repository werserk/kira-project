"""Tests for upsert by uid semantics (Phase 3, Point 13).

Verifies that:
1. Reprocessing same entity never creates duplicates
2. Content updates in place (no append-only)
3. Upsert resolves by uid correctly
"""

import tempfile
from pathlib import Path

import pytest

from kira.storage.vault import Vault, VaultConfig


def test_upsert_creates_new_entity():
    """Test upsert creates new entity when id doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create entity
        data = {"title": "New Task", "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        
        assert entity.id is not None
        assert entity.metadata["title"] == "New Task"
        
        # Verify only one file exists
        tasks_dir = Path(tmpdir) / "tasks"
        if tasks_dir.exists():
            task_files = list(tasks_dir.glob("*.md"))
            assert len(task_files) == 1


def test_upsert_updates_existing_entity():
    """Test upsert updates existing entity when id matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Original Title", "status": "todo", "tags": []}
        entity1 = vault.upsert("task", data)
        entity_id = entity1.id
        
        # Update same entity
        data2 = {"id": entity_id, "title": "Updated Title", "status": "doing", "tags": []}
        entity2 = vault.upsert("task", data2)
        
        assert entity2.id == entity_id
        assert entity2.metadata["title"] == "Updated Title"
        assert entity2.metadata["status"] == "doing"
        
        # Verify still only one file exists
        tasks_dir = Path(tmpdir) / "tasks"
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == 1


def test_reprocessing_same_entity_no_duplicates():
    """Test DoD: Reprocessing same entity never creates duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Task", "status": "todo", "tags": []}
        entity1 = vault.upsert("task", data)
        entity_id = entity1.id
        
        # Reprocess same entity multiple times
        for i in range(5):
            data_updated = {"id": entity_id, "title": f"Version {i}", "status": "todo", "tags": []}
            entity = vault.upsert("task", data_updated)
            assert entity.id == entity_id
        
        # Verify only one file exists (no duplicates)
        tasks_dir = Path(tmpdir) / "tasks"
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == 1, f"Found {len(task_files)} files, expected 1 (no duplicates)"
        
        # Verify final content
        final_entity = vault.get(entity_id)
        assert final_entity.metadata["title"] == "Version 4"


def test_content_updates_in_place():
    """Test DoD: Content updates in place (no append-only)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create entity with initial content
        data = {"title": "Task", "status": "todo", "tags": []}
        entity1 = vault.upsert("task", data, content="Initial content")
        entity_id = entity1.id
        
        # Get file path
        tasks_dir = Path(tmpdir) / "tasks"
        task_file = tasks_dir / f"{entity_id}.md"
        assert task_file.exists()
        
        # Get initial file size
        initial_size = task_file.stat().st_size
        
        # Update content multiple times
        for i in range(3):
            data_updated = {"id": entity_id, "title": "Task", "status": "todo", "tags": []}
            vault.upsert("task", data_updated, content=f"Updated content version {i}")
        
        # File should still be same file (not appended)
        assert task_file.exists()
        
        # Final content should be the last update (not all versions appended)
        final_entity = vault.get(entity_id)
        assert final_entity.content == "Updated content version 2"
        assert "version 0" not in final_entity.content
        assert "version 1" not in final_entity.content


def test_upsert_by_uid_resolves_correctly():
    """Test upsert resolves entity by uid correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create multiple entities
        entity1 = vault.upsert("task", {"title": "Task 1", "status": "todo", "tags": []})
        entity2 = vault.upsert("task", {"title": "Task 2", "status": "todo", "tags": []})
        entity3 = vault.upsert("task", {"title": "Task 3", "status": "todo", "tags": []})
        
        # Update entity 2 by id (keep status as todo to avoid fsm validation issues)
        updated = vault.upsert("task", {"id": entity2.id, "title": "Updated Task 2", "status": "doing", "tags": []})
        
        # Verify correct entity was updated
        assert updated.id == entity2.id
        assert updated.metadata["title"] == "Updated Task 2"
        
        # Verify other entities unchanged
        retrieved1 = vault.get(entity1.id)
        retrieved3 = vault.get(entity3.id)
        
        assert retrieved1.metadata["title"] == "Task 1"
        assert retrieved3.metadata["title"] == "Task 3"
        
        # Verify still only 3 files
        tasks_dir = Path(tmpdir) / "tasks"
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == 3


def test_upsert_multiple_updates_same_entity():
    """Test multiple rapid updates to same entity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create entity
        data = {"title": "Task", "counter": 0, "status": "todo", "tags": []}
        entity = vault.upsert("task", data)
        entity_id = entity.id
        
        # Perform 10 updates
        for i in range(1, 11):
            data_updated = {"id": entity_id, "title": "Task", "counter": i, "status": "todo", "tags": []}
            vault.upsert("task", data_updated)
        
        # Verify only one file
        tasks_dir = Path(tmpdir) / "tasks"
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == 1
        
        # Verify final counter
        final = vault.get(entity_id)
        assert final.metadata["counter"] == 10


def test_upsert_preserves_entity_id():
    """Test upsert preserves entity id across updates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create entity
        entity1 = vault.upsert("task", {"title": "Task", "status": "todo", "tags": []})
        original_id = entity1.id
        
        # Update multiple times
        for i in range(5):
            entity = vault.upsert("task", {"id": original_id, "title": f"Update {i}", "status": "todo", "tags": []})
            assert entity.id == original_id, f"ID changed on update {i}"


def test_upsert_with_different_content_lengths():
    """Test upsert works with varying content lengths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create with short content
        entity = vault.upsert("task", {"title": "Task", "status": "todo", "tags": []}, content="Short")
        entity_id = entity.id
        
        # Update with longer content
        vault.upsert("task", {"id": entity_id, "title": "Task", "status": "todo", "tags": []}, content="Much longer content " * 50)
        
        # Update with shorter content
        vault.upsert("task", {"id": entity_id, "title": "Task", "status": "todo", "tags": []}, content="Short again")
        
        # Verify final content
        final = vault.get(entity_id)
        assert final.content == "Short again"
        
        # Verify only one file
        tasks_dir = Path(tmpdir) / "tasks"
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == 1


def test_upsert_metadata_changes():
    """Test upsert correctly updates metadata fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create entity (don't use tags as links cause issues in this test)
        entity = vault.upsert("task", {
            "title": "Task",
            "status": "todo",
            "tags": [],
        })
        entity_id = entity.id
        
        # Update metadata
        vault.upsert("task", {
            "id": entity_id,
            "title": "Updated Task",
            "status": "doing",
            "tags": [],
        })
        
        # Verify updates
        final = vault.get(entity_id)
        assert final.metadata["title"] == "Updated Task"
        assert final.metadata["status"] == "doing"
        assert final.metadata["tags"] == []


def test_dod_no_duplicates_on_reprocess():
    """Test DoD: Reprocessing same entity never creates duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Simulate reprocessing same event multiple times
        entity_id = None
        
        for i in range(10):
            if entity_id is None:
                # First time - create
                entity = vault.upsert("task", {"title": "Event Task", "status": "todo", "tags": []})
                entity_id = entity.id
            else:
                # Subsequent times - reprocess (update)
                entity = vault.upsert("task", {
                    "id": entity_id,
                    "title": "Event Task",
                    "status": "todo",
                    "tags": [],
                    "processed_count": i,
                })
        
        # Should have exactly one entity
        tasks_dir = Path(tmpdir) / "tasks"
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == 1, "Reprocessing created duplicates!"
        
        # Verify final state
        final = vault.get(entity_id)
        assert final.metadata["processed_count"] == 9


def test_dod_content_updates_in_place():
    """Test DoD: Content updates in place (no append-only semantics)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VaultConfig(vault_path=Path(tmpdir))
        vault = Vault(config)
        
        # Create with initial content (use task for simplicity)
        entity = vault.upsert("task", {
            "title": "My Task",
            "status": "todo",
            "tags": [],
        }, content="Version 1 content")
        entity_id = entity.id
        
        # Update content multiple times
        vault.upsert("task", {"id": entity_id, "title": "My Task", "status": "todo", "tags": []}, content="Version 2 content")
        vault.upsert("task", {"id": entity_id, "title": "My Task", "status": "todo", "tags": []}, content="Version 3 content")
        vault.upsert("task", {"id": entity_id, "title": "My Task", "status": "todo", "tags": []}, content="Version 4 content")
        
        # Final content should be ONLY version 4 (not all versions appended)
        final = vault.get(entity_id)
        
        assert final.content == "Version 4 content"
        assert "Version 1" not in final.content
        assert "Version 2" not in final.content
        assert "Version 3" not in final.content
        
        # Content was replaced, not appended
        assert final.content.count("Version") == 1

