"""Integration tests for plugin usage of Vault API (ADR-006).

These tests verify that plugins can successfully use ctx.vault to interact
with the Vault through the Host API, without direct filesystem access.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.events import create_event_bus
from kira.core.host import create_host_api
from kira.core.vault_facade import create_vault_facade
from kira.plugin_sdk.context import PluginContext


class TestVaultPluginIntegration:
    """Test plugin integration with Vault API."""

    def test_plugin_can_create_entity_via_vault(self, tmp_path):
        """Plugin can create entities using ctx.vault.create_entity()."""
        # Setup Host API and Vault facade
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)

        # Create plugin context with vault access
        context = PluginContext(
            config={"vault": {"path": str(tmp_path)}},
            vault=vault,
        )

        # Plugin creates entity via ctx.vault
        entity = context.vault.create_entity(
            "task",
            {"title": "Plugin-created task", "priority": "high"},
            content="Task content from plugin",
        )

        assert entity.id.startswith("task-")
        assert entity.metadata["title"] == "Plugin-created task"
        assert entity.content == "Task content from plugin"

        # Verify entity was actually created
        read_back = context.vault.read_entity(entity.id)
        assert read_back.id == entity.id
        assert read_back.metadata["title"] == "Plugin-created task"

    def test_plugin_can_read_entity_via_vault(self, tmp_path):
        """Plugin can read entities using ctx.vault.read_entity()."""
        # Setup
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)

        # Pre-create an entity
        entity = host_api.create_entity(
            "note",
            {"title": "Test Note", "content": "Note body"},
            content="# Test Note\n\nNote body",
        )

        # Create plugin context
        context = PluginContext(vault=vault)

        # Plugin reads entity
        read_entity = context.vault.read_entity(entity.id)

        assert read_entity.id == entity.id
        assert read_entity.metadata["title"] == "Test Note"

    def test_plugin_can_update_entity_via_vault(self, tmp_path):
        """Plugin can update entities using ctx.vault.update_entity()."""
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)

        # Create entity
        entity = host_api.create_entity(
            "task",
            {"title": "Original", "status": "todo"},
        )

        # Plugin updates entity
        context = PluginContext(vault=vault)
        updated = context.vault.update_entity(
            entity.id,
            {"title": "Updated", "status": "done"},
            content="Completed successfully",
        )

        assert updated.metadata["title"] == "Updated"
        assert updated.metadata["status"] == "done"
        assert updated.content == "Completed successfully"

    def test_plugin_can_delete_entity_via_vault(self, tmp_path):
        """Plugin can delete entities using ctx.vault.delete_entity()."""
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)

        # Create entity
        entity = host_api.create_entity("note", {"title": "To Delete"})

        # Plugin deletes entity
        context = PluginContext(vault=vault)
        context.vault.delete_entity(entity.id)

        # Verify deletion
        from kira.core.host import EntityNotFoundError

        with pytest.raises(EntityNotFoundError):
            context.vault.read_entity(entity.id)

    def test_plugin_can_list_entities_via_vault(self, tmp_path):
        """Plugin can list entities using ctx.vault.list_entities()."""
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)

        # Create some entities
        host_api.create_entity("task", {"title": "Task 1"})
        host_api.create_entity("task", {"title": "Task 2"})
        host_api.create_entity("note", {"title": "Note 1"})

        # Plugin lists entities
        context = PluginContext(vault=vault)

        all_entities = context.vault.list_entities()
        assert len(all_entities) == 3

        tasks = context.vault.list_entities("task")
        assert len(tasks) == 2
        assert all(e.entity_type == "task" for e in tasks)

    def test_plugin_can_search_entities_via_vault(self, tmp_path):
        """Plugin can search entities using ctx.vault.search_entities()."""
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)

        # Create entities
        host_api.create_entity(
            "task",
            {"title": "Urgent fix"},
            content="Fix bug urgently",
        )
        host_api.create_entity(
            "task",
            {"title": "Normal task"},
            content="Regular work",
        )

        # Plugin searches
        context = PluginContext(vault=vault)
        results = context.vault.search_entities("urgent")

        assert len(results) == 1
        assert "urgent" in results[0].metadata.get("title", "").lower()

    def test_plugin_can_upsert_entity_via_vault(self, tmp_path):
        """Plugin can upsert entities using ctx.vault.upsert_entity()."""
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)
        context = PluginContext(vault=vault)

        # Create new entity via upsert
        entity1 = context.vault.upsert_entity(
            "task",
            {"title": "New Task"},
            content="Task content",
        )
        assert entity1.metadata["title"] == "New Task"

        # Update existing entity via upsert
        entity2 = context.vault.upsert_entity(
            "task",
            {"id": entity1.id, "title": "Updated Task"},
            content="Updated content",
        )
        assert entity2.id == entity1.id
        assert entity2.metadata["title"] == "Updated Task"

    def test_plugin_can_get_entity_links_via_vault(self, tmp_path):
        """Plugin can retrieve entity links using ctx.vault.get_entity_links()."""
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)

        # Create linked entities
        task1 = host_api.create_entity("task", {"title": "Task 1"})
        task2 = host_api.create_entity(
            "task",
            {"title": "Task 2", "depends_on": [task1.id]},
            content=f"Related to [[{task1.id}]]",
        )

        # Plugin retrieves links
        context = PluginContext(vault=vault)
        links = context.vault.get_entity_links(task2.id)

        assert "outgoing" in links
        assert "incoming" in links
        assert len(links["outgoing"]) > 0

    def test_plugin_without_vault_access_gracefully_fails(self):
        """Plugin context without vault access handles missing vault gracefully."""
        # Create context without vault
        context = PluginContext(config={"test": "value"})

        # vault should be None
        assert context.vault is None

        # Plugin code should check for None before using
        # This is the pattern plugins should follow:
        if context.vault is not None:
            # Use vault
            pass
        else:
            # Fallback behavior or log warning
            context.logger.warning("Vault not available")

    @pytest.mark.skip(reason="Requires kira_plugin_inbox to be installed in Python path")
    def test_inbox_plugin_uses_vault_api(self, tmp_path):
        """Inbox plugin actually uses Host API when available."""
        host_api = create_host_api(tmp_path)
        vault = create_vault_facade(host_api)

        context = PluginContext(
            config={"vault": {"path": str(tmp_path)}},
            vault=vault,
        )

        # Import and activate inbox plugin
        from kira_plugin_inbox.plugin import InboxNormalizer

        normalizer = InboxNormalizer(context)

        # Process message - should use Host API
        result = normalizer.process_message("Test message", source="test")

        assert result["success"]

        # Verify entity was created via Host API
        entities = list(host_api.list_entities("note"))
        assert len(entities) >= 1

        # Check that one of the entities has inbox status
        inbox_entities = [e for e in entities if e.metadata.get("status") == "inbox"]
        assert len(inbox_entities) >= 1

    def test_events_emitted_on_vault_operations(self, tmp_path):
        """Vault operations emit events that plugins can subscribe to."""
        event_bus = create_event_bus()
        events_captured = []

        def capture_event(event) -> None:
            events_captured.append((event.name, event.payload))

        event_bus.subscribe("entity.created", capture_event)
        event_bus.subscribe("entity.updated", capture_event)
        event_bus.subscribe("entity.deleted", capture_event)

        # Setup with event bus
        host_api = create_host_api(tmp_path, event_bus=event_bus)
        vault = create_vault_facade(host_api)
        context = PluginContext(vault=vault)

        # Create entity
        entity = context.vault.create_entity("task", {"title": "Test"})
        assert len(events_captured) == 1
        assert events_captured[0][0] == "entity.created"
        assert events_captured[0][1]["entity_id"] == entity.id

        # Update entity
        context.vault.update_entity(entity.id, {"title": "Updated"})
        assert len(events_captured) == 2
        assert events_captured[1][0] == "entity.updated"

        # Delete entity
        context.vault.delete_entity(entity.id)
        assert len(events_captured) == 3
        assert events_captured[2][0] == "entity.deleted"


class TestVaultAPIPermissions:
    """Test that Vault API respects permissions and sandbox policies."""

    def test_sandbox_policy_forbids_direct_vault_fs_writes(self, tmp_path):
        """Sandbox policy should deny direct filesystem writes to Vault paths."""
        from kira.core.policy import PermissionDeniedError, Policy

        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        manifest = {
            "name": "test-plugin",
            "permissions": ["fs.write"],
            "sandbox": {
                "strategy": "subprocess",
                "fsAccess": {
                    "write": [str(tmp_path / "temp")],  # Only temp dir allowed
                },
            },
        }

        policy = Policy.from_manifest(manifest, vault_path=vault_path)

        # Plugin tries to write directly to vault - should be denied
        vault_file = vault_path / "notes" / "test.md"

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_fs_write_access(str(vault_file))

        assert "Vault" in str(exc_info.value)
        assert "Host API" in str(exc_info.value)

    def test_sandbox_policy_forbids_direct_vault_fs_reads(self, tmp_path):
        """Sandbox policy should deny direct filesystem reads from Vault paths."""
        from kira.core.policy import PermissionDeniedError, Policy

        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        manifest = {
            "name": "test-plugin",
            "permissions": ["fs.read"],
            "sandbox": {
                "fsAccess": {
                    "read": [str(tmp_path / "config")],  # Only config dir allowed
                },
            },
        }

        policy = Policy.from_manifest(manifest, vault_path=vault_path)

        # Plugin tries to read directly from vault - should be denied
        vault_file = vault_path / "notes" / "test.md"

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_fs_read_access(str(vault_file))

        assert "Vault" in str(exc_info.value)

    def test_plugin_should_use_vault_api_not_fs(self, tmp_path):
        """Demonstrate correct pattern: plugins should use vault API, not filesystem."""
        from kira.core.policy import PermissionDeniedError, Policy

        vault_path = tmp_path / "vault"
        host_api = create_host_api(vault_path)
        vault = create_vault_facade(host_api)

        # ❌ WRONG: Plugin tries direct filesystem access
        manifest_bad = {
            "name": "bad-plugin",
            "permissions": ["fs.write"],
            "sandbox": {"fsAccess": {"write": []}},
        }
        policy_bad = Policy.from_manifest(manifest_bad, vault_path=vault_path)

        with pytest.raises(PermissionDeniedError):
            policy_bad.check_fs_write_access(str(vault_path / "notes" / "test.md"))

        # ✅ CORRECT: Plugin uses Host API via ctx.vault
        context = PluginContext(vault=vault)
        entity = context.vault.create_entity(
            "note",
            {"title": "Proper way"},
            content="Using Host API",
        )
        assert entity.id is not None
        assert entity.path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
