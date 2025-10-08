"""Vault facade for plugin SDK integration (ADR-006).

This module provides a plugin-safe wrapper around HostAPI that can be
injected into PluginContext.vault and accessed via JSON-RPC from sandboxed plugins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .host import Entity, HostAPI

__all__ = [
    "VaultFacade",
    "create_vault_facade",
]


class VaultFacade:
    """Plugin-safe facade for Vault operations.

    This class implements the VaultProtocol from plugin_sdk.context and provides
    a simplified interface for plugins to interact with the Vault through the
    Host API. All operations go through validation, permission checks, and
    event emission as defined in ADR-006.

    Example:
        >>> from kira.core.host import create_host_api
        >>> from kira.core.vault_facade import create_vault_facade
        >>> host_api = create_host_api(Path("vault"))
        >>> vault = create_vault_facade(host_api)
        >>> entity = vault.create_entity("task", {"title": "My Task"})
        >>> entity.id
        'task-20250107-1234-my-task'
    """

    def __init__(self, host_api: HostAPI) -> None:
        """Initialize Vault facade.

        Parameters
        ----------
        host_api
            Host API instance to delegate operations to
        """
        self._host = host_api

    def create_entity(self, entity_type: str, data: dict[str, Any], *, content: str = "") -> Entity:
        """Create new entity in Vault.

        Parameters
        ----------
        entity_type
            Type of entity (task, note, event, etc.)
        data
            Entity metadata (frontmatter)
        content
            Markdown content body

        Returns
        -------
        Entity
            Created entity with generated ID

        Raises
        ------
        VaultError
            If creation fails (duplicate ID, validation error, etc.)

        Example:
            >>> entity = vault.create_entity(
            ...     "task",
            ...     {"title": "Fix bug", "priority": "high"},
            ...     content="Detailed description"
            ... )
        """
        return self._host.create_entity(entity_type, data, content=content)

    def read_entity(self, entity_id: str) -> Entity:
        """Read entity by ID.

        Parameters
        ----------
        entity_id
            Entity identifier

        Returns
        -------
        Entity
            Entity with metadata and content

        Raises
        ------
        EntityNotFoundError
            If entity does not exist

        Example:
            >>> entity = vault.read_entity("task-20250107-1234-fix-bug")
        """
        return self._host.read_entity(entity_id)

    def update_entity(self, entity_id: str, updates: dict[str, Any], *, content: str | None = None) -> Entity:
        """Update existing entity.

        Parameters
        ----------
        entity_id
            Entity identifier
        updates
            Metadata fields to update
        content
            Optional new content (None keeps existing)

        Returns
        -------
        Entity
            Updated entity

        Raises
        ------
        EntityNotFoundError
            If entity does not exist

        Example:
            >>> entity = vault.update_entity(
            ...     "task-123",
            ...     {"status": "done"},
            ...     content="Completed successfully"
            ... )
        """
        return self._host.update_entity(entity_id, updates, content=content)

    def delete_entity(self, entity_id: str) -> None:
        """Delete entity from Vault.

        Parameters
        ----------
        entity_id
            Entity identifier

        Raises
        ------
        EntityNotFoundError
            If entity does not exist

        Example:
            >>> vault.delete_entity("task-20250107-1234-obsolete")
        """
        self._host.delete_entity(entity_id)

    def list_entities(self, entity_type: str | None = None, *, limit: int | None = None) -> list[Entity]:
        """List entities in Vault.

        Parameters
        ----------
        entity_type
            Optional filter by entity type
        limit
            Optional maximum number of entities to return

        Returns
        -------
        list[Entity]
            List of entities

        Example:
            >>> tasks = vault.list_entities("task", limit=10)
            >>> all_entities = vault.list_entities()
        """
        return list(self._host.list_entities(entity_type, limit=limit))

    def upsert_entity(self, entity_type: str, data: dict[str, Any], *, content: str = "") -> Entity:
        """Create or update entity.

        If data contains an 'id' field and that entity exists, it will be updated.
        Otherwise, a new entity will be created.

        Parameters
        ----------
        entity_type
            Type of entity
        data
            Entity metadata (must include 'id' for update)
        content
            Markdown content

        Returns
        -------
        Entity
            Created or updated entity

        Example:
            >>> entity = vault.upsert_entity(
            ...     "task",
            ...     {"id": "task-123", "title": "Updated"},
            ...     content="New content"
            ... )
        """
        return self._host.upsert_entity(entity_type, data, content=content)

    def get_entity_links(self, entity_id: str) -> dict[str, Any]:
        """Get links for entity.

        Parameters
        ----------
        entity_id
            Entity identifier

        Returns
        -------
        dict[str, Any]
            Dictionary with 'incoming' and 'outgoing' link lists

        Example:
            >>> links = vault.get_entity_links("task-123")
            >>> incoming = links["incoming"]
            >>> outgoing = links["outgoing"]
        """
        return self._host.get_entity_links(entity_id)

    def search_entities(self, query: str, *, entity_type: str | None = None, limit: int = 50) -> list[Entity]:
        """Search entities by query.

        Parameters
        ----------
        query
            Search query (searches title and content)
        entity_type
            Optional filter by entity type
        limit
            Maximum results to return

        Returns
        -------
        list[Entity]
            Matching entities

        Example:
            >>> results = vault.search_entities("urgent", entity_type="task")
        """
        # Simple implementation - search in title and content
        results = []
        query_lower = query.lower()

        for entity in self._host.list_entities(entity_type):
            title = entity.metadata.get("title", "").lower()
            content_lower = entity.content.lower()

            if query_lower in title or query_lower in content_lower:
                results.append(entity)

            if len(results) >= limit:
                break

        return results


def create_vault_facade(host_api: HostAPI) -> VaultFacade:
    """Factory function to create VaultFacade.

    Parameters
    ----------
    host_api
        Host API instance

    Returns
    -------
    VaultFacade
        Configured facade instance

    Example:
        >>> from kira.core.host import create_host_api
        >>> from kira.core.vault_facade import create_vault_facade
        >>> host_api = create_host_api(Path("vault"))
        >>> vault = create_vault_facade(host_api)
    """
    return VaultFacade(host_api)
