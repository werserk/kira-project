"""Tests for Host API implementation (ADR-006)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.events import EventBus
from kira.core.host import Entity, EntityNotFoundError, HostAPI, VaultError, create_host_api
from kira.core.schemas import SchemaCache


class TestEntity:
    def test_entity_creation(self):
        entity = Entity(
            id="task-test-123",
            entity_type="task",
            metadata={"title": "Test Task", "status": "todo"},
            content="Task content",
        )

        assert entity.id == "task-test-123"
        assert entity.entity_type == "task"
        assert entity.get_title() == "Test Task"

    def test_entity_get_title_from_content(self):
        entity = Entity(
            id="note-123",
            entity_type="note",
            metadata={},
            content="# Important Note\n\nContent here",
        )

        assert entity.get_title() == "Important Note"

    def test_entity_to_markdown(self):
        entity = Entity(
            id="task-123",
            entity_type="task",
            metadata={"title": "Test", "priority": "high"},
            content="Task description",
        )

        doc = entity.to_markdown()

        assert doc.frontmatter["id"] == "task-123"
        assert doc.frontmatter["title"] == "Test"
        assert doc.content == "Task description"


class TestHostAPI:
    def test_create_host_api(self, tmp_path):
        host_api = create_host_api(tmp_path)

        assert host_api.vault_path == tmp_path
        assert isinstance(host_api.link_graph, object)

    def test_vault_structure_creation(self, tmp_path):
        HostAPI(tmp_path)

        assert (tmp_path / ".kira").exists()
        assert (tmp_path / ".kira" / "schemas").exists()
        assert (tmp_path / "inbox").exists()
        assert (tmp_path / "processed").exists()

    def test_create_entity_basic(self, tmp_path):
        host_api = HostAPI(tmp_path)

        entity = host_api.create_entity(
            "task",
            {"title": "Test Task", "priority": "high"},
            content="Task description",
        )

        assert entity.id.startswith("task-")
        assert entity.entity_type == "task"
        assert entity.metadata["title"] == "Test Task"
        assert entity.content == "Task description"

        # Check file was created
        assert entity.path.exists()

    def test_create_entity_with_id(self, tmp_path):
        host_api = HostAPI(tmp_path)

        entity = host_api.create_entity(
            "note",
            {"id": "note-custom-123", "title": "Custom Note"},
            content="Note content",
        )

        assert entity.id == "note-custom-123"
        assert entity.path.exists()

    def test_create_entity_duplicate_id(self, tmp_path):
        host_api = HostAPI(tmp_path)

        # Create first entity
        host_api.create_entity("task", {"id": "task-123", "title": "Task 1"})

        # Try to create duplicate
        with pytest.raises(VaultError) as exc_info:
            host_api.create_entity("task", {"id": "task-123", "title": "Task 2"})

        assert "already exists" in str(exc_info.value)

    def test_read_entity(self, tmp_path):
        host_api = HostAPI(tmp_path)

        # Create entity
        created = host_api.create_entity(
            "task",
            {"title": "Test Task", "priority": "medium"},
            content="Original content",
        )

        # Read it back
        read_entity = host_api.read_entity(created.id)

        assert read_entity.id == created.id
        assert read_entity.metadata["title"] == "Test Task"
        assert read_entity.content == "Original content"

    def test_read_entity_not_found(self, tmp_path):
        host_api = HostAPI(tmp_path)

        with pytest.raises(EntityNotFoundError):
            host_api.read_entity("task-nonexistent-123")

    def test_update_entity(self, tmp_path):
        host_api = HostAPI(tmp_path)

        # Create entity
        entity = host_api.create_entity(
            "task",
            {"title": "Original Title", "status": "todo"},
            content="Original content",
        )

        original_updated = entity.metadata["updated"]

        # Update entity
        updated = host_api.update_entity(
            entity.id,
            {"title": "Updated Title", "status": "doing"},
            content="Updated content",
        )

        assert updated.metadata["title"] == "Updated Title"
        assert updated.metadata["status"] == "doing"
        assert updated.content == "Updated content"
        assert updated.metadata["updated"] > original_updated

    def test_delete_entity(self, tmp_path):
        host_api = HostAPI(tmp_path)

        # Create entity
        entity = host_api.create_entity("note", {"title": "To Delete"})
        entity_id = entity.id

        # Delete it
        host_api.delete_entity(entity_id)

        # Should not exist anymore
        with pytest.raises(EntityNotFoundError):
            host_api.read_entity(entity_id)

        assert not entity.path.exists()

    def test_upsert_entity_create(self, tmp_path):
        host_api = HostAPI(tmp_path)

        entity = host_api.upsert_entity(
            "task",
            {"title": "New Task"},
            content="Task content",
        )

        assert entity.id.startswith("task-")
        assert entity.metadata["title"] == "New Task"

    def test_upsert_entity_update(self, tmp_path):
        host_api = HostAPI(tmp_path)

        # Create entity
        original = host_api.create_entity("task", {"title": "Original"})

        # Upsert with same ID
        updated = host_api.upsert_entity(
            "task",
            {"id": original.id, "title": "Updated", "priority": "high"},
            content="Updated content",
        )

        assert updated.id == original.id
        assert updated.metadata["title"] == "Updated"
        assert updated.content == "Updated content"

    def test_list_entities(self, tmp_path):
        host_api = HostAPI(tmp_path)

        # Create some entities
        host_api.create_entity("task", {"title": "Task 1"})
        host_api.create_entity("task", {"title": "Task 2"})
        host_api.create_entity("note", {"title": "Note 1"})

        # List all entities
        all_entities = list(host_api.list_entities())
        assert len(all_entities) == 3

        # List only tasks
        tasks = list(host_api.list_entities("task"))
        assert len(tasks) == 2
        assert all(e.entity_type == "task" for e in tasks)

    def test_list_entities_with_limit(self, tmp_path):
        host_api = HostAPI(tmp_path)

        # Create entities
        for i in range(5):
            host_api.create_entity("task", {"title": f"Task {i}"})

        # Test limit and offset
        limited = list(host_api.list_entities(limit=2))
        assert len(limited) == 2

        offset_limited = list(host_api.list_entities(limit=2, offset=2))
        assert len(offset_limited) == 2

    def test_get_entity_links(self, tmp_path):
        host_api = HostAPI(tmp_path)

        # Create entities with links
        task1 = host_api.create_entity("task", {"title": "Task 1"})
        task2 = host_api.create_entity(
            "task",
            {"title": "Task 2", "depends_on": [task1.id]},
            content=f"This task mentions [[{task1.id}]]",
        )

        links = host_api.get_entity_links(task2.id)

        assert "outgoing" in links
        assert "incoming" in links
        assert len(links["outgoing"]) > 0

    def test_event_emission(self, tmp_path):
        event_bus = EventBus()
        events: list[tuple[str, dict]] = []

        def capture_events(event) -> None:
            events.append((event.name, event.payload))

        event_bus.subscribe("entity.created", capture_events)
        event_bus.subscribe("entity.updated", capture_events)
        event_bus.subscribe("entity.deleted", capture_events)

        host_api = HostAPI(tmp_path, event_bus=event_bus)

        # Create entity
        entity = host_api.create_entity("task", {"title": "Test"})
        assert len(events) == 1
        assert events[0][0] == "entity.created"
        assert events[0][1]["entity_id"] == entity.id

        # Update entity
        host_api.update_entity(entity.id, {"title": "Updated"})
        assert len(events) == 2
        assert events[1][0] == "entity.updated"

        # Delete entity
        host_api.delete_entity(entity.id)
        assert len(events) == 3
        assert events[2][0] == "entity.deleted"

    def test_invalid_entity_id(self, tmp_path):
        host_api = HostAPI(tmp_path)

        with pytest.raises(VaultError) as exc_info:
            host_api.create_entity("task", {"id": "invalid-id-format!"})

        assert "Invalid entity ID" in str(exc_info.value)


class TestVaultErrorHandling:
    def test_vault_error_inheritance(self):
        error = VaultError("Test error")
        assert isinstance(error, Exception)

    def test_entity_not_found_error_inheritance(self):
        error = EntityNotFoundError("Entity not found")
        assert isinstance(error, VaultError)
        assert isinstance(error, Exception)


class TestHostAPIFactory:
    def test_create_host_api(self, tmp_path):
        host_api = create_host_api(tmp_path)

        assert isinstance(host_api, HostAPI)
        assert host_api.vault_path == tmp_path

    def test_create_host_api_with_components(self, tmp_path):
        event_bus = EventBus()
        schema_cache = SchemaCache()

        host_api = create_host_api(
            tmp_path,
            event_bus=event_bus,
            schema_cache=schema_cache,
        )

        assert host_api.event_bus is event_bus
        assert host_api.schema_cache is schema_cache
