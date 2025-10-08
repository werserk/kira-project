"""Integration tests for Phase 0 requirements (DoD verification).

Tests:
1. Persistent clarification queue - survives process restart
2. Plugin entry point alignment - loads without sys.path hacks
3. Host API in PluginContext - plugins can upsert via Host API
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


@pytest.fixture
def vault_with_host_api(tmp_path: Path):
    """Create vault with Host API."""
    from kira.core.host import create_host_api
    from kira.core.vault_facade import create_vault_facade
    
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    
    # Create Host API
    host_api = create_host_api(vault_path)
    
    # Create Vault facade for plugins
    vault_facade = create_vault_facade(host_api)
    
    return {
        "vault_path": vault_path,
        "host_api": host_api,
        "vault_facade": vault_facade,
    }


@pytest.fixture
def inbox_plugin_path():
    """Get inbox plugin path."""
    import kira
    
    kira_root = Path(kira.__file__).parent
    plugin_path = kira_root / "plugins" / "inbox"
    
    if not plugin_path.exists():
        pytest.skip("Inbox plugin not found")
    
    return plugin_path


class TestClarificationQueuePersistence:
    """Test clarification queue persistence (Phase 0, Task 1)."""

    def test_queue_survives_restart(self, tmp_path: Path):
        """Verify clarification queue persists across restarts.
        
        DoD: process restart does not lose pending clarifications; 
        test: create 2 items → restart → continue.
        """
        from kira.plugins.inbox.clarification_queue import ClarificationQueue
        
        storage_path = tmp_path / "clarifications.json"
        
        # First session: create 2 items
        queue1 = ClarificationQueue(storage_path)
        
        item1 = queue1.add(
            source_event_id="evt-001",
            extracted_type="task",
            extracted_data={"title": "First task", "content": "Do something"},
            confidence=0.65,
        )
        
        item2 = queue1.add(
            source_event_id="evt-002",
            extracted_type="note",
            extracted_data={"title": "Second note", "content": "Remember this"},
            confidence=0.70,
            alternatives=[{"type": "task", "confidence": 0.5}],
        )
        
        # Verify items were created
        assert item1.clarification_id.startswith("clarif-")
        assert item2.clarification_id.startswith("clarif-")
        
        # Simulate restart: create new queue instance
        queue2 = ClarificationQueue(storage_path)
        
        # Verify items were restored
        pending = queue2.get_pending()
        assert len(pending) == 2
        
        # Verify data integrity
        ids = {item.clarification_id for item in pending}
        assert item1.clarification_id in ids
        assert item2.clarification_id in ids
        
        # Verify all fields are preserved
        restored_item1 = next(i for i in pending if i.clarification_id == item1.clarification_id)
        assert restored_item1.source_event_id == "evt-001"
        assert restored_item1.extracted_type == "task"
        assert restored_item1.confidence == 0.65
        assert restored_item1.extracted_data["title"] == "First task"
        
        restored_item2 = next(i for i in pending if i.clarification_id == item2.clarification_id)
        assert len(restored_item2.suggested_alternatives) == 1
        assert restored_item2.suggested_alternatives[0]["type"] == "task"

    def test_queue_serialization_format(self, tmp_path: Path):
        """Verify queue uses proper JSON serialization."""
        from kira.plugins.inbox.clarification_queue import ClarificationQueue
        
        storage_path = tmp_path / "clarifications.json"
        queue = ClarificationQueue(storage_path)
        
        queue.add(
            source_event_id="evt-test",
            extracted_type="meeting",
            extracted_data={"title": "Team sync"},
            confidence=0.8,
        )
        
        # Verify file exists and has valid JSON
        assert storage_path.exists()
        
        with open(storage_path) as f:
            data = json.load(f)
        
        # Verify structure
        assert "version" in data
        assert "items" in data
        assert len(data["items"]) == 1
        
        item = data["items"][0]
        assert "clarification_id" in item
        assert "source_event_id" in item
        assert "extracted_type" in item
        assert "extracted_data" in item
        assert "confidence" in item
        assert "created_at" in item
        assert "status" in item


class TestPluginEntryPoint:
    """Test plugin entry point alignment (Phase 0, Task 2)."""

    def test_plugin_loads_without_sys_path_hacks(self, inbox_plugin_path: Path):
        """Verify plugin loads via manifest entry without sys.path manipulation.
        
        DoD: plugin starts from a clean env via `entry` without extra steps.
        """
        from kira.core.plugin_loader import PluginLoader
        from kira.plugin_sdk.context import PluginContext
        
        # Create loader with clean context
        context = PluginContext(config={"vault": {"path": "./vault"}})
        loader = PluginLoader(context=context, use_sandbox=False)
        
        # Load plugin
        result = loader.load_plugin(inbox_plugin_path)
        
        # Verify plugin loaded successfully
        assert result["name"] == "kira-inbox"
        assert result["result"]["status"] == "ok"
        assert "version" in result["result"]

    def test_plugin_imports_are_clean(self, inbox_plugin_path: Path):
        """Verify plugin module can be imported without side effects."""
        import sys
        import importlib
        
        # Add plugin src to path temporarily
        plugin_src = inbox_plugin_path / "src"
        sys.path.insert(0, str(plugin_src))
        
        try:
            # Import should work cleanly
            plugin_module = importlib.import_module("kira_plugin_inbox.plugin")
            
            # Verify activate function exists
            assert hasattr(plugin_module, "activate")
            assert callable(plugin_module.activate)
            
        finally:
            # Clean up
            if str(plugin_src) in sys.path:
                sys.path.remove(str(plugin_src))


class TestHostAPIIntegration:
    """Test Host API in PluginContext (Phase 0, Task 3)."""

    def test_plugin_context_receives_host_api(self, vault_with_host_api):
        """Verify PluginContext can be created with Host API."""
        from kira.plugin_sdk.context import PluginContext
        
        vault_facade = vault_with_host_api["vault_facade"]
        
        # Create context with vault
        context = PluginContext(vault=vault_facade)
        
        # Verify vault is accessible
        assert context.vault is not None
        assert context.vault == vault_facade

    def test_plugin_uses_host_api_for_upsert(self, vault_with_host_api, inbox_plugin_path: Path):
        """Verify plugin uses Host API when available.
        
        DoD: when Host API exists, plugin never uses fallback; 
        integration test shows `upsert` by `uid`.
        """
        from kira.core.plugin_loader import PluginLoader
        from kira.plugin_sdk.context import PluginContext
        
        vault_path = vault_with_host_api["vault_path"]
        vault_facade = vault_with_host_api["vault_facade"]
        
        # Create context with vault access
        context = PluginContext(
            config={"vault": {"path": str(vault_path)}},
            vault=vault_facade,
        )
        
        # Load plugin with vault-enabled context
        loader = PluginLoader(context=context, use_sandbox=False, vault=vault_facade)
        loader.load_plugin(inbox_plugin_path)
        
        # Get normalizer and process a message with high confidence
        from kira_plugin_inbox.plugin import get_normalizer
        
        normalizer = get_normalizer()
        
        # Process message with high confidence (above threshold)
        result = normalizer.process_message(
            message="Urgent: Fix the critical bug in authentication",
            source="test"
        )
        
        # Verify entity was created via Host API (not fallback)
        assert result.get("success") is True
        assert "entity_id" in result
        assert "file_path" not in result  # Would be present if using fallback
        
        # Verify entity exists in vault
        entity_id = result["entity_id"]
        entity = vault_facade.read_entity(entity_id)
        
        assert entity.id == entity_id
        assert entity.metadata.get("title") is not None
        assert entity.metadata.get("source") == "test"

    def test_plugin_loader_accepts_vault_parameter(self, vault_with_host_api):
        """Verify PluginLoader accepts vault parameter."""
        from kira.core.plugin_loader import PluginLoader
        
        vault_facade = vault_with_host_api["vault_facade"]
        vault_path = vault_with_host_api["vault_path"]
        
        # Create loader with vault
        loader = PluginLoader(
            vault_path=vault_path,
            vault=vault_facade,
            use_sandbox=False,
        )
        
        # Verify context has vault access
        assert loader.context.vault is not None
        assert loader.context.vault == vault_facade


class TestPhase0Complete:
    """Comprehensive test for all Phase 0 requirements."""

    def test_all_phase0_requirements(self, tmp_path: Path, inbox_plugin_path: Path):
        """Verify all Phase 0 tasks are complete.
        
        This test combines all requirements:
        1. Persistent clarification queue
        2. Clean plugin loading
        3. Host API integration
        """
        from kira.core.host import create_host_api
        from kira.core.plugin_loader import PluginLoader
        from kira.core.vault_facade import create_vault_facade
        from kira.plugins.inbox.clarification_queue import ClarificationQueue
        
        # Setup vault and Host API
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        host_api = create_host_api(vault_path)
        vault_facade = create_vault_facade(host_api)
        
        # 1. Test clarification queue persistence
        clarifications_path = vault_path / ".kira" / "clarifications.json"
        queue1 = ClarificationQueue(clarifications_path)
        
        item = queue1.add(
            source_event_id="evt-phase0",
            extracted_type="task",
            extracted_data={"title": "Phase 0 test", "content": "Verify all requirements"},
            confidence=0.6,
        )
        
        # Restart queue
        queue2 = ClarificationQueue(clarifications_path)
        pending = queue2.get_pending()
        assert len(pending) == 1
        assert pending[0].clarification_id == item.clarification_id
        
        # 2. Test plugin loading with Host API
        loader = PluginLoader(
            vault_path=vault_path,
            vault=vault_facade,
            use_sandbox=False,
        )
        
        result = loader.load_plugin(inbox_plugin_path)
        assert result["result"]["status"] == "ok"
        
        # 3. Test Host API usage
        from kira_plugin_inbox.plugin import get_normalizer
        
        normalizer = get_normalizer()
        
        # High confidence message should use Host API
        process_result = normalizer.process_message(
            message="TODO: Complete Phase 0 implementation",
            source="integration_test"
        )
        
        assert process_result.get("success") is True
        assert "entity_id" in process_result
        
        # Verify entity in vault
        entity = vault_facade.read_entity(process_result["entity_id"])
        assert entity.id == process_result["entity_id"]
        
        # Low confidence message should queue for clarification
        low_conf_result = normalizer.process_message(
            message="maybe something",
            source="integration_test"
        )
        
        assert low_conf_result.get("requires_clarification") is True
        assert "request_id" in low_conf_result
        
        # Verify clarification was queued
        pending_after = queue2.get_pending()
        assert len(pending_after) == 2  # Original + new one

