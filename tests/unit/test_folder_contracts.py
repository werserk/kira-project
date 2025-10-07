"""Tests for folder contracts implementation (ADR-007)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.host import HostAPI, VaultError
from kira.core.vault_init import init_vault


class TestFolderContracts:
    def test_entity_placement_by_type(self, tmp_path):
        """Test entities are placed in correct folders by type."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        host_api = HostAPI(vault_path)

        # Create entities of different types
        task = host_api.create_entity("task", {"title": "Test Task", "status": "todo"})
        note = host_api.create_entity("note", {"title": "Test Note"})
        project = host_api.create_entity("project", {"title": "Test Project", "status": "active"})

        # Check they're in correct folders
        assert task.path.parent.name == "tasks"
        assert note.path.parent.name == "notes"
        assert project.path.parent.name == "projects"

    def test_folder_contract_violation_required_fields(self, tmp_path):
        """Test folder contract enforcement for required fields."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        host_api = HostAPI(vault_path)

        # Try to create task without required status field
        with pytest.raises(VaultError) as exc_info:
            host_api.create_entity("task", {"title": "Incomplete Task"})

        assert "Folder contract violations" in str(exc_info.value)
        assert "status" in str(exc_info.value)

    def test_filename_pattern_enforcement(self, tmp_path):
        """Test filename follows pattern from folder contracts."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        host_api = HostAPI(vault_path)

        task = host_api.create_entity(
            "task",
            {"id": "task-custom-123", "title": "Custom Task", "status": "todo"}
        )

        # Check filename follows pattern {id}.md
        assert task.path.name == "task-custom-123.md"
        assert task.path.suffix == ".md"

    def test_entity_type_folder_mapping(self, tmp_path):
        """Test all entity types map to correct folders."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        host_api = HostAPI(vault_path)

        test_entities = [
            ("task", "tasks"),
            ("note", "notes"),
            ("event", "events"),
            ("project", "projects"),
            ("contact", "contacts"),
            ("meeting", "meetings"),
        ]

        for entity_type, expected_folder in test_entities:
            folder = host_api._get_folder_for_entity_type(entity_type)
            assert folder == expected_folder

    def test_unknown_entity_type_fallback(self, tmp_path):
        """Test unknown entity types fall back to processed folder."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        host_api = HostAPI(vault_path)

        folder = host_api._get_folder_for_entity_type("unknown")
        assert folder == "processed"

    def test_contract_violations_detection(self, tmp_path):
        """Test detection of folder contract violations."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        host_api = HostAPI(vault_path)

        # Test with incomplete metadata
        violations = host_api._enforce_folder_contracts("task", {"title": "Test"})

        assert len(violations) > 0
        assert any("Missing required frontmatter field" in v for v in violations)

    def test_valid_contract_compliance(self, tmp_path):
        """Test valid entities pass contract checks."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        host_api = HostAPI(vault_path)

        # Complete task metadata
        task_data = {
            "id": "task-valid-123",
            "title": "Valid Task",
            "status": "todo",
            "created": "2025-01-15T12:00:00Z",
        }

        violations = host_api._enforce_folder_contracts("task", task_data)

        assert len(violations) == 0


class TestVaultStructureValidation:
    def test_validate_vault_structure_complete(self, tmp_path):
        """Test validation of complete vault structure."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        issues = verify_vault_structure(vault_path)

        assert len(issues) == 0

    def test_validate_vault_structure_missing_dirs(self, tmp_path):
        """Test validation detects missing directories."""
        vault_path = tmp_path / "incomplete"
        vault_path.mkdir()

        issues = verify_vault_structure(vault_path)

        assert len(issues) > 0
        assert any(".kira" in issue for issue in issues)
        assert any("inbox" in issue for issue in issues)

    def test_validate_vault_structure_missing_schemas(self, tmp_path):
        """Test validation detects missing schemas."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        (vault_path / ".kira").mkdir()
        (vault_path / ".kira" / "schemas").mkdir()
        (vault_path / "inbox").mkdir()
        (vault_path / "processed").mkdir()
        (vault_path / "tasks").mkdir()
        (vault_path / "notes").mkdir()
        (vault_path / "projects").mkdir()

        issues = verify_vault_structure(vault_path)

        assert len(issues) > 0
        assert any("Missing required schema" in issue for issue in issues)

    def test_validate_vault_structure_invalid_json_schema(self, tmp_path):
        """Test validation detects invalid JSON schemas."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        # Corrupt a schema file
        task_schema_file = vault_path / ".kira" / "schemas" / "task.json"
        task_schema_file.write_text("invalid json content")

        issues = verify_vault_structure(vault_path)

        assert len(issues) > 0
        assert any("Invalid JSON" in issue for issue in issues)


class TestVaultInfo:
    def test_get_vault_info_initialized(self, tmp_path):
        """Test getting info for initialized vault."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        # Create some test entities
        host_api = HostAPI(vault_path)
        host_api.create_entity("task", {"title": "Task 1", "status": "todo"})
        host_api.create_entity("note", {"title": "Note 1"})

        info = get_vault_info(vault_path)

        assert info["structure_valid"] is True
        assert info["entity_counts"]["tasks"] >= 1
        assert info["entity_counts"]["notes"] >= 1
        assert info["schema_count"] >= 4

    def test_get_vault_info_with_inbox_items(self, tmp_path):
        """Test vault info includes inbox and processed counts."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        # Add some inbox items
        (vault_path / "inbox" / "test1.txt").write_text("test content")
        (vault_path / "inbox" / "test2.txt").write_text("test content")

        info = get_vault_info(vault_path)

        assert info["inbox_items"] >= 2
        assert "processed_items" in info


class TestSchemaEvolution:
    def test_schema_version_tracking(self):
        """Test schemas have version information."""
        schemas = create_default_schemas()

        for entity_type, schema in schemas.items():
            assert "version" in schema
            assert isinstance(schema["version"], str)
            assert len(schema["version"]) > 0

    def test_schema_backwards_compatibility_check(self, tmp_path):
        """Test schema compatibility checking (placeholder)."""
        # This would be expanded for real schema evolution testing
        schemas = create_default_schemas()

        # All current schemas should be version 1.0.0
        for entity_type, schema in schemas.items():
            assert schema["version"] == "1.0.0"
