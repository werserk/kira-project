"""Tests for Vault schemas and folder contracts (ADR-007)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.schemas import (
    EntitySchema,
    SchemaCache,
    SchemaValidationError,
    ValidationResult,
    create_default_schemas,
    get_schema_cache,
    validate_entity,
    validate_vault_structure,
)
from kira.core.vault_init import VaultInitError, get_vault_info, init_vault, install_schemas, verify_vault_structure


class TestDefaultSchemas:
    def test_create_default_schemas(self):
        """Test creating default schemas."""
        schemas = create_default_schemas()

        assert "task" in schemas
        assert "note" in schemas
        assert "event" in schemas
        assert "project" in schemas

        # Validate task schema structure
        task_schema = schemas["task"]
        assert task_schema["type"] == "object"
        assert "id" in task_schema["required"]
        assert "title" in task_schema["required"]
        assert "status" in task_schema["required"]

    def test_schema_has_folder_contracts(self):
        """Test schemas include folder contract information."""
        schemas = create_default_schemas()

        for entity_type, schema in schemas.items():
            assert "folder_contracts" in schema
            contracts = schema["folder_contracts"]
            assert "allowed_locations" in contracts
            assert "filename_pattern" in contracts
            assert "required_frontmatter" in contracts

    def test_entity_id_patterns(self):
        """Test entity ID patterns in schemas."""
        schemas = create_default_schemas()

        patterns = {
            "task": r"^task-[a-z0-9][a-z0-9-]*[a-z0-9]$",
            "note": r"^note-[a-z0-9][a-z0-9-]*[a-z0-9]$",
            "event": r"^event-[a-z0-9][a-z0-9-]*[a-z0-9]$",
            "project": r"^project-[a-z0-9][a-z0-9-]*[a-z0-9]$",
        }

        for entity_type, expected_pattern in patterns.items():
            schema = schemas[entity_type]
            actual_pattern = schema["properties"]["id"]["pattern"]
            assert actual_pattern == expected_pattern


class TestEntitySchema:
    def test_entity_schema_validation_valid(self):
        """Test entity schema validation with valid data."""
        schema_data = {
            "type": "object",
            "required": ["id", "title"],
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string", "minLength": 1},
            },
        }
        schema = EntitySchema("test", schema_data)

        data = {"id": "test-123", "title": "Test Entity"}
        result = schema.validate(data)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_entity_schema_validation_invalid(self):
        """Test entity schema validation with invalid data."""
        schema_data = {
            "type": "object",
            "required": ["id", "title"],
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string", "minLength": 1},
            },
        }
        schema = EntitySchema("test", schema_data)

        # Missing required field
        data = {"id": "test-123"}
        result = schema.validate(data)

        assert result.valid is False
        assert len(result.errors) > 0
        assert "title" in str(result.errors[0])

    def test_entity_schema_get_defaults(self):
        """Test extracting default values from schema."""
        schema_data = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "default": "pending"},
                "priority": {"type": "string", "default": "medium"},
                "optional": {"type": "string"},
            },
        }
        schema = EntitySchema("test", schema_data)

        defaults = schema.get_default_values()

        assert defaults["status"] == "pending"
        assert defaults["priority"] == "medium"
        assert "optional" not in defaults


class TestSchemaCache:
    def test_schema_cache_no_dir(self, tmp_path):
        """Test schema cache without schemas directory."""
        cache = SchemaCache(tmp_path / "nonexistent")
        cache.load_schemas()

        # Should load default schemas
        entity_types = cache.get_entity_types()
        assert len(entity_types) > 0
        assert "task" in entity_types

    def test_schema_cache_with_dir(self, tmp_path):
        """Test schema cache with schemas directory."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()

        # Create test schema
        test_schema = {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "string"}},
        }

        (schemas_dir / "test.json").write_text(json.dumps(test_schema))

        cache = SchemaCache(schemas_dir)
        cache.load_schemas()

        schema = cache.get_schema("test")
        assert schema is not None
        assert schema.entity_type == "test"

    def test_schema_cache_validation(self, tmp_path):
        """Test entity validation through cache."""
        cache = SchemaCache()  # Uses defaults

        # Valid task
        task_data = {
            "id": "task-test-123",
            "title": "Test Task",
            "status": "todo",
            "created": "2025-01-15T12:00:00Z",
        }

        result = cache.validate_entity("task", task_data)
        assert result.valid is True

        # Invalid task (missing required field)
        invalid_data = {"id": "task-test-123"}
        result = cache.validate_entity("task", invalid_data)
        assert result.valid is False

    def test_schema_cache_unknown_type(self, tmp_path):
        """Test validation of unknown entity type."""
        cache = SchemaCache()

        result = cache.validate_entity("unknown", {"id": "test"})
        assert result.valid is False
        assert "No schema found" in result.errors[0]


class TestVaultInit:
    def test_init_vault(self, tmp_path):
        """Test initializing new vault."""
        vault_path = tmp_path / "test_vault"

        init_vault(vault_path)

        # Check structure was created
        assert (vault_path / ".kira").exists()
        assert (vault_path / ".kira" / "schemas").exists()
        assert (vault_path / "inbox").exists()
        assert (vault_path / "tasks").exists()

        # Check schemas were installed
        assert (vault_path / ".kira" / "schemas" / "task.json").exists()
        assert (vault_path / ".kira" / "schemas" / "note.json").exists()

    def test_init_vault_existing_noforce(self, tmp_path):
        """Test initializing vault with existing content without force."""
        vault_path = tmp_path / "existing_vault"
        vault_path.mkdir()
        (vault_path / "existing_file.txt").write_text("content")

        with pytest.raises(VaultInitError) as exc_info:
            init_vault(vault_path, force=False)

        assert "not empty" in str(exc_info.value)

    def test_init_vault_existing_force(self, tmp_path):
        """Test initializing vault with force overwrite."""
        vault_path = tmp_path / "existing_vault"
        vault_path.mkdir()
        (vault_path / "existing_file.txt").write_text("content")

        # Should succeed with force
        init_vault(vault_path, force=True)

        assert (vault_path / ".kira").exists()

    def test_install_schemas(self, tmp_path):
        """Test installing schemas."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        install_schemas(vault_path)

        schemas_dir = vault_path / ".kira" / "schemas"
        assert schemas_dir.exists()

        schema_files = list(schemas_dir.glob("*.json"))
        assert len(schema_files) >= 4  # task, note, event, project

        # Validate schema content
        task_schema_file = schemas_dir / "task.json"
        assert task_schema_file.exists()

        with open(task_schema_file) as f:
            task_schema = json.load(f)

        assert task_schema["type"] == "object"
        assert "id" in task_schema["required"]

    def test_verify_vault_structure_valid(self, tmp_path):
        """Test verifying valid vault structure."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        issues = verify_vault_structure(vault_path)

        assert len(issues) == 0

    def test_verify_vault_structure_invalid(self, tmp_path):
        """Test verifying invalid vault structure."""
        vault_path = tmp_path / "incomplete_vault"
        vault_path.mkdir()

        issues = verify_vault_structure(vault_path)

        assert len(issues) > 0
        assert any("Missing required directory" in issue for issue in issues)

    def test_get_vault_info(self, tmp_path):
        """Test getting vault information."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        info = get_vault_info(vault_path)

        assert info["vault_path"] == str(vault_path)
        assert info["structure_valid"] is True
        assert "entity_counts" in info
        assert "schema_count" in info
        assert info["schema_count"] >= 4

    def test_get_vault_info_nonexistent(self, tmp_path):
        """Test getting info for non-existent vault."""
        info = get_vault_info(tmp_path / "nonexistent")

        assert "error" in info
        assert "does not exist" in info["error"]


class TestValidationResult:
    def test_validation_result_valid(self):
        """Test valid validation result."""
        result = ValidationResult(valid=True, errors=[])

        assert result.valid is True
        assert bool(result) is True
        assert str(result) == "Valid"

    def test_validation_result_invalid(self):
        """Test invalid validation result."""
        result = ValidationResult(valid=False, errors=["Error 1", "Error 2"])

        assert result.valid is False
        assert bool(result) is False
        assert "Error 1" in str(result)
        assert "Error 2" in str(result)


class TestStandaloneValidation:
    def test_validate_entity_function(self):
        """Test standalone validate_entity function."""
        entity_data = {
            "id": "task-test-123",
            "title": "Test Task",
            "status": "todo",
            "created": "2025-01-15T12:00:00Z",
        }

        result = validate_entity("task", entity_data)

        assert result.valid is True

    def test_validate_vault_structure(self, tmp_path):
        """Test validate_vault_structure function."""
        # Empty directory
        issues = validate_vault_structure(str(tmp_path))
        assert len(issues) > 0

        # Initialize vault
        init_vault(tmp_path / "vault")
        issues = validate_vault_structure(str(tmp_path / "vault"))
        assert len(issues) == 0


class TestADR007Compliance:
    def test_schemas_are_json_schema_draft7(self):
        """Test all schemas use JSON Schema Draft-07."""
        schemas = create_default_schemas()

        for entity_type, schema in schemas.items():
            assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"

    def test_schemas_have_version_and_id(self):
        """Test all schemas have version and $id fields."""
        schemas = create_default_schemas()

        for entity_type, schema in schemas.items():
            assert "$id" in schema
            assert "version" in schema
            assert schema["$id"].startswith("https://kira.schema/")
            assert schema["$id"].endswith(f"{entity_type}.json")

    def test_folder_contracts_completeness(self):
        """Test folder contracts have required fields."""
        schemas = create_default_schemas()

        required_contract_fields = [
            "allowed_locations",
            "filename_pattern",
            "required_frontmatter",
        ]

        for entity_type, schema in schemas.items():
            assert "folder_contracts" in schema
            contracts = schema["folder_contracts"]

            for field in required_contract_fields:
                assert field in contracts, f"Missing {field} in {entity_type} folder contracts"

    def test_entity_id_consistency(self):
        """Test entity ID patterns are consistent."""
        schemas = create_default_schemas()

        for entity_type, schema in schemas.items():
            id_pattern = schema["properties"]["id"]["pattern"]
            expected_prefix = f"^{entity_type}-"
            assert id_pattern.startswith(expected_prefix)

    def test_required_frontmatter_consistency(self):
        """Test required frontmatter matches schema required fields."""
        schemas = create_default_schemas()

        for entity_type, schema in schemas.items():
            schema_required = set(schema["required"])
            contract_required = set(schema["folder_contracts"]["required_frontmatter"])

            # Contract required should be subset of schema required
            assert contract_required.issubset(schema_required), (
                f"Folder contract required fields not in schema for {entity_type}: "
                f"contract={contract_required}, schema={schema_required}"
            )
