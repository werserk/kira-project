"""Vault initialization and schema setup (ADR-007).

Provides utilities to initialize Vault structure, install schemas,
and create folder contracts.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .schemas import create_default_schemas

__all__ = [
    "VaultInitError",
    "init_vault",
    "install_schemas",
    "verify_vault_structure",
]


class VaultInitError(Exception):
    """Raised when Vault initialization fails."""

    pass


def init_vault(vault_path: Path | str, *, force: bool = False) -> None:
    """Initialize Vault with schemas and folder structure.

    Parameters
    ----------
    vault_path
        Path to Vault directory
    force
        Overwrite existing Vault if True

    Raises
    ------
    VaultInitError
        If initialization fails
    """
    vault_path = Path(vault_path)

    # Check if Vault exists
    if vault_path.exists() and not force:
        if any(vault_path.iterdir()):
            raise VaultInitError(
                f"Vault directory is not empty: {vault_path}. Use force=True to overwrite."
            )

    try:
        # Create directory structure
        _create_vault_structure(vault_path)

        # Install schemas
        install_schemas(vault_path)

        # Install folder contracts
        _install_folder_contracts(vault_path)

        # Create example entities
        _create_example_entities(vault_path)

    except Exception as exc:
        raise VaultInitError(f"Failed to initialize Vault: {exc}") from exc


def _create_vault_structure(vault_path: Path) -> None:
    """Create basic Vault directory structure.

    Parameters
    ----------
    vault_path
        Vault root directory
    """
    directories = [
        vault_path,
        vault_path / ".kira",
        vault_path / ".kira" / "schemas",
        vault_path / ".kira" / "index",
        vault_path / ".kira" / "config",
        vault_path / "inbox",
        vault_path / "inbox" / "raw",
        vault_path / "processed",
        vault_path / "tasks",
        vault_path / "tasks" / "active",
        vault_path / "tasks" / "completed",
        vault_path / "tasks" / "blocked",
        vault_path / "tasks" / "archived",
        vault_path / "notes",
        vault_path / "notes" / "ideas",
        vault_path / "notes" / "research",
        vault_path / "notes" / "summaries",
        vault_path / "notes" / "references",
        vault_path / "events",
        vault_path / "projects",
        vault_path / "projects" / "active",
        vault_path / "projects" / "archived",
        vault_path / "contacts",
        vault_path / "meetings",
        vault_path / "journal",
        vault_path / "resources",
        vault_path / "archive",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def install_schemas(vault_path: Path | str, *, source_schemas: dict[str, dict[str, Any]] | None = None) -> None:
    """Install JSON schemas into Vault.

    Parameters
    ----------
    vault_path
        Vault root directory
    source_schemas
        Optional custom schemas (uses defaults if not provided)

    Raises
    ------
    VaultInitError
        If schema installation fails
    """
    vault_path = Path(vault_path)
    schemas_dir = vault_path / ".kira" / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    schemas = source_schemas or create_default_schemas()

    try:
        for entity_type, schema_data in schemas.items():
            schema_file = schemas_dir / f"{entity_type}.json"

            with open(schema_file, "w", encoding="utf-8") as f:
                json.dump(schema_data, f, indent=2, ensure_ascii=False)

    except Exception as exc:
        raise VaultInitError(f"Failed to install schemas: {exc}") from exc


def _install_folder_contracts(vault_path: Path) -> None:
    """Install folder contract README files.

    Parameters
    ----------
    vault_path
        Vault root directory
    """
    # Get the project root to find contract templates
    project_root = Path(__file__).parent.parent.parent.parent
    contracts_source = project_root / "vault"

    contracts = {
        "tasks": "tasks/README.md",
        "notes": "notes/README.md",
        "projects": "projects/README.md",
        "inbox": "inbox/README.md",
        "processed": "processed/README.md",
        ".kira": ".kira/README.md",
    }

    for folder, contract_file in contracts.items():
        source_file = contracts_source / contract_file
        target_file = vault_path / contract_file

        if source_file.exists():
            # Copy contract file
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)


def _create_example_entities(vault_path: Path) -> None:
    """Create example entities to demonstrate structure.

    Parameters
    ----------
    vault_path
        Vault root directory
    """
    # Create example task
    task_example = vault_path / "tasks" / "task-example-welcome.md"
    task_content = """---
id: task-example-welcome
title: Welcome to your Kira Vault
status: todo
priority: medium
created: 2025-01-15T12:00:00Z
tags: [example, onboarding]
description: Get familiar with task management
---

# Welcome to your Kira Vault

This is an example task to help you understand the structure.

## Getting Started
1. Review the folder contracts in each directory
2. Explore the schemas in `.kira/schemas/`
3. Try creating your own entities

## Next Steps
- [[note-example-vault-guide]] - Read the vault guide
- Delete this example when ready

*This is an example entity. Feel free to delete it once you're familiar with the system.*
"""

    # Create example note
    note_example = vault_path / "notes" / "note-example-vault-guide.md"
    note_content = """---
id: note-example-vault-guide
title: Kira Vault User Guide
category: reference
created: 2025-01-15T12:00:00Z
tags: [guide, reference, onboarding]
importance: high
---

# Kira Vault User Guide

## Overview
Your Kira Vault is a structured knowledge base using Markdown files with YAML frontmatter.

## Entity Types
- **Tasks**: Actionable items with status tracking
- **Notes**: Information, ideas, and research
- **Events**: Calendar events and meetings
- **Projects**: Larger initiatives with goals
- **Contacts**: People and organizations
- **Meetings**: Meeting notes with action items

## Folder Structure
Each entity type has its own folder with specific rules (see folder READMEs).

## Working with Entities
- Use the CLI: `./kira vault new --type task --title "My Task"`
- Edit files directly with any Markdown editor
- Links between entities: `[[entity-id]]`
- Tags for organization: `#work #urgent`

## Automation
- Inbox processes incoming messages
- Calendar syncs with Google Calendar
- Tasks trigger notifications and timeboxing
- Links maintain consistency automatically

*This is an example entity. Keep it as a reference or delete when ready.*
"""

    try:
        task_example.write_text(task_content, encoding="utf-8")
        note_example.write_text(note_content, encoding="utf-8")
    except Exception:
        # Not critical if examples fail
        pass


def verify_vault_structure(vault_path: Path | str) -> list[str]:
    """Verify Vault has correct structure and schemas.

    Parameters
    ----------
    vault_path
        Vault root directory

    Returns
    -------
    list[str]
        List of issues found (empty if valid)
    """
    vault_path = Path(vault_path)
    issues = []

    if not vault_path.exists():
        return [f"Vault directory does not exist: {vault_path}"]

    # Check required directories
    required_dirs = [
        ".kira",
        ".kira/schemas",
        "inbox",
        "processed",
        "tasks",
        "notes",
        "projects",
    ]

    for dir_name in required_dirs:
        dir_path = vault_path / dir_name
        if not dir_path.exists():
            issues.append(f"Missing required directory: {dir_name}")

    # Check required schemas
    schemas_dir = vault_path / ".kira" / "schemas"
    required_schemas = ["task.json", "note.json", "event.json", "project.json"]

    for schema_name in required_schemas:
        schema_file = schemas_dir / schema_name
        if not schema_file.exists():
            issues.append(f"Missing required schema: {schema_name}")
        else:
            # Validate schema is valid JSON
            try:
                with open(schema_file, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError:
                issues.append(f"Invalid JSON in schema: {schema_name}")

    # Check folder contracts
    contract_folders = ["tasks", "notes", "projects", "inbox", "processed", ".kira"]
    for folder in contract_folders:
        readme_file = vault_path / folder / "README.md"
        if not readme_file.exists():
            issues.append(f"Missing folder contract: {folder}/README.md")

    return issues


def get_vault_info(vault_path: Path | str) -> dict[str, Any]:
    """Get information about Vault structure and content.

    Parameters
    ----------
    vault_path
        Vault root directory

    Returns
    -------
    dict[str, Any]
        Vault information
    """
    vault_path = Path(vault_path)

    if not vault_path.exists():
        return {"error": "Vault does not exist"}

    # Count entities by type
    entity_counts = {}
    for entity_dir in ["tasks", "notes", "events", "projects", "contacts", "meetings"]:
        entity_path = vault_path / entity_dir
        if entity_path.exists():
            count = len(list(entity_path.rglob("*.md")))
            entity_counts[entity_dir] = count
        else:
            entity_counts[entity_dir] = 0

    # Check inbox status
    inbox_path = vault_path / "inbox"
    processed_path = vault_path / "processed"

    inbox_count = len(list(inbox_path.rglob("*"))) if inbox_path.exists() else 0
    processed_count = len(list(processed_path.rglob("*.md"))) if processed_path.exists() else 0

    # Get schema info
    schemas_dir = vault_path / ".kira" / "schemas"
    schema_count = len(list(schemas_dir.glob("*.json"))) if schemas_dir.exists() else 0

    return {
        "vault_path": str(vault_path),
        "structure_valid": len(verify_vault_structure(vault_path)) == 0,
        "entity_counts": entity_counts,
        "inbox_items": inbox_count,
        "processed_items": processed_count,
        "schema_count": schema_count,
        "issues": verify_vault_structure(vault_path),
    }
