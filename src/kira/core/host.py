"""Host API for Vault operations (ADR-006, Phase 1 Point 5).

Single point of access for all Vault operations with validation,
ID generation, link maintenance, and event emission.

Phase 1, Point 5: Domain validation before every write.
Invalid entities never touch disk; errors are surfaced to callers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .events import EventBus
from .ids import generate_entity_id, is_valid_entity_id, parse_entity_id
from .links import LinkGraph, update_entity_links
from .md_io import MarkdownDocument, MarkdownIOError, read_markdown, write_markdown
from .quarantine import quarantine_invalid_entity
from .schemas import SchemaCache, get_schema_cache
from .validation import ValidationError, validate_entity

__all__ = [
    "Entity",
    "EntityNotFoundError",
    "HostAPI",
    "VaultError",
    "ValidationError",
    "create_host_api",
]


class VaultError(Exception):
    """Base exception for Vault operations."""

    pass


class EntityNotFoundError(VaultError):
    """Raised when entity is not found."""

    pass


@dataclass
class Entity:
    """Vault entity with metadata and content."""

    id: str
    entity_type: str
    metadata: dict[str, Any]
    content: str
    path: Path | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_markdown(cls, entity_id: str, document: MarkdownDocument, file_path: Path | None = None) -> Entity:
        """Create entity from Markdown document.

        Parameters
        ----------
        entity_id
            Entity identifier
        document
            Markdown document
        file_path
            Optional file path

        Returns
        -------
        Entity
            Created entity
        """
        # Parse entity type from ID
        parsed_id = parse_entity_id(entity_id)

        # Extract timestamps
        created_str = document.get_metadata("created")
        updated_str = document.get_metadata("updated")

        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        if created_str:
            try:
                created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        if updated_str:
            try:
                updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return cls(
            id=entity_id,
            entity_type=parsed_id.entity_type,
            metadata=document.frontmatter.copy(),
            content=document.content,
            path=file_path,
            created_at=created_at,
            updated_at=updated_at,
        )

    def to_markdown(self) -> MarkdownDocument:
        """Convert entity to Markdown document.

        Returns
        -------
        MarkdownDocument
            Markdown representation
        """
        # Ensure metadata has required fields
        metadata = self.metadata.copy()
        metadata["id"] = self.id
        metadata["created"] = self.created_at.isoformat()
        metadata["updated"] = self.updated_at.isoformat()

        return MarkdownDocument(frontmatter=metadata, content=self.content)

    def get_title(self) -> str:
        """Get entity title from metadata or content.

        Returns
        -------
        str
            Entity title
        """
        # Try metadata first
        title = self.metadata.get("title")
        if title:
            return str(title)

        # Extract from first line of content
        if self.content:
            first_line = self.content.split("\n")[0].strip()
            if first_line.startswith("#"):
                return first_line.lstrip("#").strip()
            return first_line[:50]  # First 50 chars

        return self.id


class HostAPI:
    """Host API for Vault operations (ADR-006).

    Provides the single point of access for all Vault mutations with:
    - Schema validation (ADR-007)
    - ID generation and collision prevention (ADR-008)
    - Link graph maintenance (ADR-016)
    - Event emission (ADR-005)
    - Atomic file operations
    """

    def __init__(
        self,
        vault_path: Path,
        *,
        event_bus: EventBus | None = None,
        schema_cache: SchemaCache | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize Host API.

        Parameters
        ----------
        vault_path
            Path to Vault directory
        event_bus
            Optional event bus for emitting events
        schema_cache
            Optional schema cache for validation
        logger
            Optional logger for structured logging
        """
        self.vault_path = Path(vault_path)
        self.event_bus = event_bus
        self.schema_cache = schema_cache or get_schema_cache(self.vault_path / ".kira" / "schemas")
        self.logger = logger
        self.link_graph = LinkGraph()

        # Ensure Vault structure
        self._ensure_vault_structure()

        # Load existing entities into link graph
        self._load_link_graph()

    def _ensure_vault_structure(self) -> None:
        """Ensure Vault has required directory structure."""
        required_dirs = [
            self.vault_path,
            self.vault_path / ".kira",
            self.vault_path / ".kira" / "schemas",
            self.vault_path / "inbox",
            self.vault_path / "processed",
        ]

        for dir_path in required_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _load_link_graph(self) -> None:
        """Load existing entities into link graph."""
        try:
            for entity in self.list_entities():
                self.link_graph.add_entity(entity.id)
                update_entity_links(self.link_graph, entity.id, entity.metadata, entity.content)
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Failed to load link graph: {exc}")

    def create_entity(self, entity_type: str, data: dict[str, Any], *, content: str = "") -> Entity:
        """Create new entity in Vault.

        Parameters
        ----------
        entity_type
            Type of entity (task, note, event, etc.)
        data
            Entity metadata
        content
            Markdown content

        Returns
        -------
        Entity
            Created entity

        Raises
        ------
        VaultError
            If creation fails
        """
        # Generate ID if not provided
        entity_id = data.get("id")
        if not entity_id:
            title = data.get("title", "")
            entity_id = generate_entity_id(entity_type, title=title)
            data = data.copy()
            data["id"] = entity_id
        else:
            # Validate provided ID
            if not is_valid_entity_id(entity_id):
                raise VaultError(f"Invalid entity ID: {entity_id}")

        # Check for duplicates
        if self._entity_exists(entity_id):
            raise VaultError(f"Entity already exists: {entity_id}")

        # Add timestamps
        now = datetime.now(timezone.utc)
        data = data.copy()
        data.setdefault("created", now.isoformat())
        data["updated"] = now.isoformat()

        # Phase 1, Point 5: Domain validation before write
        # Invalid entities never touch disk
        validation_result = validate_entity(entity_type, data)
        if not validation_result.valid:
            # Phase 1, Point 6: Quarantine invalid entities
            quarantine_dir = self.vault_path / "artifacts" / "quarantine"
            quarantine_invalid_entity(
                entity_type=entity_type,
                payload=data,
                errors=validation_result.errors,
                reason=f"Validation failed for {entity_type}",
                quarantine_dir=quarantine_dir,
            )
            
            raise ValidationError(
                f"Entity validation failed for {entity_type} '{entity_id}'",
                errors=validation_result.errors,
            )

        # Validate against schema (legacy, now part of validate_entity)
        if self.schema_cache:
            validation_result_schema = self.schema_cache.validate_entity(entity_type, data)
            if not validation_result_schema:
                raise VaultError(f"Schema validation failed: {'; '.join(validation_result_schema.errors)}")

        # Enforce folder contracts (ADR-007)
        contract_violations = self._enforce_folder_contracts(entity_type, data)
        if contract_violations:
            raise VaultError(f"Folder contract violations: {'; '.join(contract_violations)}")

        # Create entity
        entity = Entity(
            id=entity_id,
            entity_type=entity_type,
            metadata=data,
            content=content,
            created_at=now,
            updated_at=now,
        )

        # Write to filesystem
        file_path = self._get_entity_path(entity_id)
        document = entity.to_markdown()

        try:
            write_markdown(file_path, document, atomic=True, create_dirs=True)
            entity.path = file_path
        except MarkdownIOError as exc:
            raise VaultError(f"Failed to write entity {entity_id}: {exc}") from exc

        # Update link graph
        self.link_graph.add_entity(entity_id)
        update_entity_links(self.link_graph, entity_id, entity.metadata, entity.content)

        # Emit event
        if self.event_bus:
            self.event_bus.publish(
                "entity.created",
                {
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "path": str(file_path),
                    "metadata": data,
                },
            )

        # Log operation
        if self.logger:
            self.logger.info(
                f"Entity created: {entity_id}",
                extra={
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "path": str(file_path),
                },
            )

        return entity

    def read_entity(self, entity_id: str) -> Entity:
        """Read entity by ID.

        Parameters
        ----------
        entity_id
            Entity identifier

        Returns
        -------
        Entity
            Entity data

        Raises
        ------
        EntityNotFoundError
            If entity not found
        """
        if not is_valid_entity_id(entity_id):
            raise VaultError(f"Invalid entity ID: {entity_id}")

        file_path = self._get_entity_path(entity_id)

        if not file_path.exists():
            raise EntityNotFoundError(f"Entity not found: {entity_id}")

        try:
            document = read_markdown(file_path)
            entity = Entity.from_markdown(entity_id, document, file_path)
            return entity
        except MarkdownIOError as exc:
            raise VaultError(f"Failed to read entity {entity_id}: {exc}") from exc

    def update_entity(self, entity_id: str, updates: dict[str, Any], *, content: str | None = None) -> Entity:
        """Update existing entity.

        Parameters
        ----------
        entity_id
            Entity identifier
        updates
            Metadata updates to apply
        content
            Optional content update

        Returns
        -------
        Entity
            Updated entity

        Raises
        ------
        EntityNotFoundError
            If entity not found
        VaultError
            If update fails
        """
        # Read current entity
        entity = self.read_entity(entity_id)

        # Apply updates
        new_metadata = entity.metadata.copy()
        new_metadata.update(updates)
        new_metadata["updated"] = datetime.now(timezone.utc).isoformat()

        new_content = content if content is not None else entity.content

        # Phase 1, Point 5: Domain validation before write
        validation_result = validate_entity(entity.entity_type, new_metadata)
        if not validation_result.valid:
            # Phase 1, Point 6: Quarantine invalid updates
            quarantine_dir = self.vault_path / "artifacts" / "quarantine"
            quarantine_invalid_entity(
                entity_type=entity.entity_type,
                payload=new_metadata,
                errors=validation_result.errors,
                reason=f"Update validation failed for {entity.entity_type}",
                quarantine_dir=quarantine_dir,
            )
            
            raise ValidationError(
                f"Entity validation failed for {entity.entity_type} '{entity_id}'",
                errors=validation_result.errors,
            )

        # Validate updates (legacy)
        if self.schema_cache:
            validation_result_schema = self.schema_cache.validate_entity(entity.entity_type, new_metadata)
            if not validation_result_schema:
                raise VaultError(f"Schema validation failed: {'; '.join(validation_result_schema.errors)}")

        # Update entity
        entity.metadata = new_metadata
        entity.content = new_content
        entity.updated_at = datetime.now(timezone.utc)

        # Write to filesystem
        document = entity.to_markdown()
        if entity.path is None:
            raise VaultError(f"Entity {entity_id} has no file path")
        try:
            write_markdown(entity.path, document, atomic=True)
        except MarkdownIOError as exc:
            raise VaultError(f"Failed to update entity {entity_id}: {exc}") from exc

        # Update link graph
        update_entity_links(self.link_graph, entity_id, entity.metadata, entity.content)

        # Emit event
        if self.event_bus:
            self.event_bus.publish(
                "entity.updated",
                {
                    "entity_id": entity_id,
                    "entity_type": entity.entity_type,
                    "path": str(entity.path),
                    "changes": updates,
                },
            )

        # Log operation
        if self.logger:
            self.logger.info(
                f"Entity updated: {entity_id}",
                extra={
                    "entity_id": entity_id,
                    "changes": list(updates.keys()),
                },
            )

        return entity

    def delete_entity(self, entity_id: str) -> None:
        """Delete entity from Vault.

        Parameters
        ----------
        entity_id
            Entity identifier

        Raises
        ------
        EntityNotFoundError
            If entity not found
        VaultError
            If deletion fails
        """
        # Read entity first
        entity = self.read_entity(entity_id)

        # Remove from link graph
        removed_links = self.link_graph.remove_entity(entity_id)

        # Delete file
        try:
            if entity.path and entity.path.exists():
                entity.path.unlink()
        except OSError as exc:
            raise VaultError(f"Failed to delete entity file {entity_id}: {exc}") from exc

        # Emit event
        if self.event_bus:
            self.event_bus.publish(
                "entity.deleted",
                {
                    "entity_id": entity_id,
                    "entity_type": entity.entity_type,
                    "path": str(entity.path) if entity.path else None,
                },
            )

        # Log operation
        if self.logger:
            self.logger.info(
                f"Entity deleted: {entity_id}",
                extra={
                    "entity_id": entity_id,
                    "removed_links": len(removed_links),
                },
            )

    def list_entities(
        self,
        entity_type: str | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> Iterator[Entity]:
        """List entities in Vault.

        Parameters
        ----------
        entity_type
            Optional entity type filter
        limit
            Optional result limit
        offset
            Result offset for pagination

        Yields
        ------
        Entity
            Vault entities
        """
        count = 0
        skipped = 0

        # Determine which folders to search
        if entity_type:
            # Search specific folder for this entity type
            folders = [self._get_folder_for_entity_type(entity_type)]
        else:
            # Search all known folders
            folders = ["tasks", "notes", "events", "projects", "contacts", "meetings", "processed"]

        for folder_name in folders:
            folder_path = self.vault_path / folder_name
            if not folder_path.exists():
                continue

            for md_file in folder_path.glob("*.md"):
                try:
                    # Read the file to get the actual ID
                    document = read_markdown(md_file)
                    entity_id = document.get_metadata("id")

                    if not entity_id or not is_valid_entity_id(entity_id):
                        continue

                    # Filter by entity type if specified
                    if entity_type:
                        parsed_id = parse_entity_id(entity_id)
                        if parsed_id.entity_type != entity_type:
                            continue

                    # Handle pagination
                    if skipped < offset:
                        skipped += 1
                        continue

                    # Create entity
                    entity = Entity.from_markdown(entity_id, document, md_file)
                    yield entity

                    count += 1
                    if limit and count >= limit:
                        return

                except Exception:
                    # Skip malformed files
                    continue

    def upsert_entity(self, entity_type: str, data: dict[str, Any], *, content: str = "") -> Entity:
        """Create or update entity.

        Parameters
        ----------
        entity_type
            Type of entity
        data
            Entity metadata
        content
            Markdown content

        Returns
        -------
        Entity
            Created or updated entity
        """
        entity_id = data.get("id")

        if entity_id and self._entity_exists(entity_id):
            # Update existing
            updates = {k: v for k, v in data.items() if k != "id"}
            return self.update_entity(entity_id, updates, content=content)
        else:
            # Create new
            return self.create_entity(entity_type, data, content=content)

    def get_entity_links(self, entity_id: str) -> dict[str, Any]:
        """Get entity link information.

        Parameters
        ----------
        entity_id
            Entity identifier

        Returns
        -------
        dict[str, Any]
            Link information
        """
        outgoing = self.link_graph.get_outgoing_links(entity_id)
        incoming = self.link_graph.get_incoming_links(entity_id)

        return {
            "outgoing": [{"target": link.target_id, "type": link.link_type} for link in outgoing],
            "incoming": [{"source": link.source_id, "type": link.link_type} for link in incoming],
        }

    def _entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists.

        Parameters
        ----------
        entity_id
            Entity identifier

        Returns
        -------
        bool
            True if entity exists
        """
        file_path = self._get_entity_path(entity_id)
        return file_path.exists()

    def _get_entity_path(self, entity_id: str) -> Path:
        """Get file path for entity following folder contracts.

        Parameters
        ----------
        entity_id
            Entity identifier

        Returns
        -------
        Path
            File path based on entity type and folder contracts
        """
        # Parse entity type from ID
        try:
            parsed_id = parse_entity_id(entity_id)
            entity_type = parsed_id.entity_type
        except ValueError:
            # Fallback to processed for invalid IDs
            return self.vault_path / "processed" / f"{entity_id}.md"

        # Apply folder contracts (ADR-007)
        folder_mapping = {
            "task": "tasks",
            "note": "notes",
            "event": "events",
            "project": "projects",
            "contact": "contacts",
            "meeting": "meetings",
        }

        folder = folder_mapping.get(entity_type, "processed")
        return self.vault_path / folder / f"{entity_id}.md"

    def _get_folder_for_entity_type(self, entity_type: str) -> str:
        """Get folder name for entity type.

        Parameters
        ----------
        entity_type
            Entity type

        Returns
        -------
        str
            Folder name
        """
        folder_mapping = {
            "task": "tasks",
            "note": "notes",
            "event": "events",
            "project": "projects",
            "contact": "contacts",
            "meeting": "meetings",
        }
        return folder_mapping.get(entity_type, "processed")

    def _enforce_folder_contracts(self, entity_type: str, metadata: dict[str, Any]) -> list[str]:
        """Enforce folder contract rules for entity.

        Parameters
        ----------
        entity_type
            Entity type
        metadata
            Entity metadata

        Returns
        -------
        list[str]
            List of contract violations (empty if valid)
        """
        violations = []

        # Get schema to check folder contracts
        if self.schema_cache:
            schema = self.schema_cache.get_schema(entity_type)
            if schema and "folder_contracts" in schema.schema:
                contracts = schema.schema["folder_contracts"]

                # Check required frontmatter fields
                required_fields = contracts.get("required_frontmatter", [])
                for field in required_fields:
                    if field not in metadata or not metadata[field]:
                        violations.append(f"Missing required frontmatter field: {field}")

        return violations


def create_host_api(
    vault_path: Path | str,
    *,
    event_bus: EventBus | None = None,
    schema_cache: SchemaCache | None = None,
    logger: Any = None,
) -> HostAPI:
    """Create Host API instance.

    Parameters
    ----------
    vault_path
        Path to Vault directory
    event_bus
        Optional event bus
    schema_cache
        Optional schema cache
    logger
        Optional logger

    Returns
    -------
    HostAPI
        Host API instance
    """
    return HostAPI(
        vault_path=Path(vault_path),
        event_bus=event_bus,
        schema_cache=schema_cache,
        logger=logger,
    )
