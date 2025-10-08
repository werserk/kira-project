"""Schema validation and management for Vault entities (ADR-007).

Provides JSON Schema validation, caching, and entity type management
for consistent data validation across the system.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]

__all__ = [
    "EntitySchema",
    "SchemaCache",
    "SchemaValidationError",
    "ValidationResult",
    "create_default_schemas",
    "get_schema_cache",
    "validate_entity",
    "validate_vault_structure",
]


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class ValidationResult:
    """Result of schema validation."""

    def __init__(self, valid: bool, errors: list[str] | None = None) -> None:
        self.valid = valid
        self.errors = errors or []

    def __bool__(self) -> bool:
        """Boolean conversion."""
        return self.valid

    def __str__(self) -> str:
        """String representation."""
        if self.valid:
            return "Valid"
        return f"Invalid: {'; '.join(self.errors)}"


class EntitySchema:
    """Container for entity schema definition."""

    def __init__(self, entity_type: str, schema: dict[str, Any]) -> None:
        """Initialize entity schema.

        Parameters
        ----------
        entity_type
            Type of entity (task, note, event, etc.)
        schema
            JSON Schema definition
        """
        self.entity_type = entity_type
        self.schema = schema
        self._validator = jsonschema.Draft7Validator(schema)

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """Validate data against schema.

        Parameters
        ----------
        data
            Data to validate

        Returns
        -------
        ValidationResult
            Validation result
        """
        errors = []

        for error in self._validator.iter_errors(data):
            error_path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
            errors.append(f"[{error_path}] {error.message}")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def get_default_values(self) -> dict[str, Any]:
        """Get default values from schema.

        Returns
        -------
        dict[str, Any]
            Default values
        """
        defaults = {}

        def extract_defaults(schema_part: dict[str, Any], path: str = "") -> None:
            if isinstance(schema_part, dict):
                if "default" in schema_part:
                    if path:
                        defaults[path] = schema_part["default"]

                if "properties" in schema_part:
                    for prop, prop_schema in schema_part["properties"].items():
                        new_path = f"{path}.{prop}" if path else prop
                        extract_defaults(prop_schema, new_path)

        extract_defaults(self.schema)
        return defaults


class SchemaCache:
    """Cache for entity schemas with automatic loading and refresh."""

    def __init__(self, schemas_dir: Path | None = None) -> None:
        """Initialize schema cache.

        Parameters
        ----------
        schemas_dir
            Directory containing schema files
        """
        self.schemas_dir = schemas_dir
        self._schemas: dict[str, EntitySchema] = {}
        self._loaded = False

    def load_schemas(self, force_reload: bool = False) -> None:
        """Load schemas from directory.

        Parameters
        ----------
        force_reload
            Force reload even if already loaded

        Raises
        ------
        SchemaValidationError
            If loading fails
        """
        if self._loaded and not force_reload:
            return

        self._schemas.clear()

        if not self.schemas_dir or not self.schemas_dir.exists():
            # No schemas directory, load defaults
            self._load_default_schemas()
            self._loaded = True
            return

        try:
            schema_files = list(self.schemas_dir.glob("*.json"))

            if not schema_files:
                # Directory exists but is empty, load defaults
                self._load_default_schemas()
            else:
                # Load schemas from files
                for schema_file in schema_files:
                    entity_type = schema_file.stem

                    with open(schema_file, encoding="utf-8") as f:
                        schema_data = json.load(f)

                    schema = EntitySchema(entity_type, schema_data)
                    self._schemas[entity_type] = schema

            self._loaded = True

        except Exception as exc:
            raise SchemaValidationError(f"Failed to load schemas from {self.schemas_dir}: {exc}") from exc

    def get_schema(self, entity_type: str) -> EntitySchema | None:
        """Get schema for entity type.

        Parameters
        ----------
        entity_type
            Type of entity

        Returns
        -------
        EntitySchema or None
            Schema if found
        """
        if not self._loaded:
            self.load_schemas()

        return self._schemas.get(entity_type)

    def validate_entity(self, entity_type: str, data: dict[str, Any]) -> ValidationResult:
        """Validate entity data.

        Parameters
        ----------
        entity_type
            Type of entity
        data
            Entity data

        Returns
        -------
        ValidationResult
            Validation result
        """
        schema = self.get_schema(entity_type)

        if not schema:
            return ValidationResult(valid=False, errors=[f"No schema found for entity type: {entity_type}"])

        return schema.validate(data)

    def get_entity_types(self) -> list[str]:
        """Get list of known entity types.

        Returns
        -------
        list[str]
            Entity types
        """
        if not self._loaded:
            self.load_schemas()

        return list(self._schemas.keys())

    def _load_default_schemas(self) -> None:
        """Load default schemas."""
        default_schemas = create_default_schemas()

        for entity_type, schema_data in default_schemas.items():
            schema = EntitySchema(entity_type, schema_data)
            self._schemas[entity_type] = schema


def create_default_schemas() -> dict[str, dict[str, Any]]:
    """Create default entity schemas.

    Returns
    -------
    dict[str, dict[str, Any]]
        Default schemas by entity type
    """
    return {
        "task": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://kira.schema/task.json",
            "version": "1.0.0",
            "type": "object",
            "required": ["id", "title", "status", "created"],
            "properties": {
                "id": {"type": "string", "pattern": r"^task-[a-z0-9][a-z0-9-]*[a-z0-9]$"},
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "description": {"type": "string"},
                "status": {"type": "string", "enum": ["todo", "doing", "review", "done", "blocked"], "default": "todo"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "default": "medium"},
                "due_date": {"type": "string", "format": "date-time"},
                "created": {"type": "string", "format": "date-time"},
                "updated": {"type": "string", "format": "date-time"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "relates_to": {"type": "array", "items": {"type": "string"}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
            },
            "folder_contracts": {
                "allowed_locations": ["tasks/", "projects/"],
                "filename_pattern": r"^[a-z0-9][a-z0-9-]*[a-z0-9]\.md$",
                "required_frontmatter": ["id", "title", "status", "created"],
            },
        },
        "note": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://kira.schema/note.json",
            "version": "1.0.0",
            "type": "object",
            "required": ["id", "title", "created"],
            "properties": {
                "id": {"type": "string", "pattern": r"^note-[a-z0-9][a-z0-9-]*[a-z0-9]$"},
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "category": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "created": {"type": "string", "format": "date-time"},
                "updated": {"type": "string", "format": "date-time"},
                "source": {"type": "string"},
                "relates_to": {"type": "array", "items": {"type": "string"}},
            },
            "folder_contracts": {
                "allowed_locations": ["notes/", "projects/"],
                "filename_pattern": r"^[a-z0-9][a-z0-9-]*[a-z0-9]\.md$",
                "required_frontmatter": ["id", "title", "created"],
            },
        },
        "event": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://kira.schema/event.json",
            "version": "1.0.0",
            "type": "object",
            "required": ["id", "title", "start_time"],
            "properties": {
                "id": {"type": "string", "pattern": r"^event-[a-z0-9][a-z0-9-]*[a-z0-9]$"},
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "description": {"type": "string"},
                "start_time": {"type": "string", "format": "date-time"},
                "end_time": {"type": "string", "format": "date-time"},
                "location": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "calendar": {"type": "string"},
                "created": {"type": "string", "format": "date-time"},
                "updated": {"type": "string", "format": "date-time"},
                "relates_to": {"type": "array", "items": {"type": "string"}},
            },
            "folder_contracts": {
                "allowed_locations": ["events/", "calendar/"],
                "filename_pattern": r"^[a-z0-9][a-z0-9-]*[a-z0-9]\.md$",
                "required_frontmatter": ["id", "title", "start_time"],
            },
        },
        "project": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://kira.schema/project.json",
            "version": "1.0.0",
            "type": "object",
            "required": ["id", "title", "status"],
            "properties": {
                "id": {"type": "string", "pattern": r"^project-[a-z0-9][a-z0-9-]*[a-z0-9]$"},
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "description": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["active", "on_hold", "completed", "cancelled"],
                    "default": "active",
                },
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
                "created": {"type": "string", "format": "date-time"},
                "updated": {"type": "string", "format": "date-time"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "folder_contracts": {
                "allowed_locations": ["projects/"],
                "filename_pattern": r"^[a-z0-9][a-z0-9-]*[a-z0-9]\.md$",
                "required_frontmatter": ["id", "title", "status"],
            },
        },
    }


def validate_vault_structure(vault_path: str) -> list[str]:
    """Validate basic Vault directory structure.

    Parameters
    ----------
    vault_path
        Path to Vault

    Returns
    -------
    list[str]
        List of validation errors (empty if valid)
    """
    vault = Path(vault_path)

    if not vault.exists():
        return [f"Vault не найден: {vault_path}"]

    errors = []

    # Check required directories
    required_dirs = [".kira", "inbox"]
    for dir_name in required_dirs:
        dir_path = vault / dir_name
        if not dir_path.exists():
            errors.append(f"Отсутствует обязательная директория: {dir_name}")

    # Check schemas directory structure
    kira_dir = vault / ".kira"
    if kira_dir.exists():
        schemas_dir = kira_dir / "schemas"
        if not schemas_dir.exists():
            schemas_dir.mkdir(parents=True, exist_ok=True)

    return errors


def validate_entity(
    entity_type: str, data: dict[str, Any], schema_cache: SchemaCache | None = None
) -> ValidationResult:
    """Validate entity data against schema.

    Parameters
    ----------
    entity_type
        Type of entity
    data
        Entity data to validate
    schema_cache
        Optional schema cache (creates default if not provided)

    Returns
    -------
    ValidationResult
        Validation result
    """
    if schema_cache is None:
        schema_cache = get_schema_cache()

    return schema_cache.validate_entity(entity_type, data)


# Global schema cache instance
_global_schema_cache: SchemaCache | None = None


def get_schema_cache(schemas_dir: Path | None = None) -> SchemaCache:
    """Get global schema cache instance.

    Parameters
    ----------
    schemas_dir
        Optional schemas directory

    Returns
    -------
    SchemaCache
        Schema cache instance
    """
    global _global_schema_cache

    if _global_schema_cache is None or schemas_dir is not None:
        _global_schema_cache = SchemaCache(schemas_dir)

    return _global_schema_cache


def validate_vault_schemas(vault_path: str) -> list[str]:
    """Legacy function for backward compatibility."""
    return validate_vault_structure(vault_path)
