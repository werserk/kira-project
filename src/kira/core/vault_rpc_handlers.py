"""RPC handlers for Vault operations (ADR-006).

This module provides RPC method handlers that the host uses to service
Vault operation requests from plugins running in sandboxed subprocesses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .host import HostAPI

__all__ = [
    "VaultRPCHandlers",
    "register_vault_rpc_handlers",
]


class VaultRPCHandlers:
    """RPC method handlers for Vault operations.

    These handlers are called by the host when plugins make RPC calls
    to vault.* methods. They validate permissions, execute operations
    through the Host API, and return results in RPC-compatible format.
    """

    def __init__(self, host_api: HostAPI) -> None:
        """Initialize Vault RPC handlers.

        Parameters
        ----------
        host_api
            Host API instance to delegate operations to
        """
        self.host_api = host_api

    def handle_vault_create(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle vault.create RPC call.

        Parameters
        ----------
        params
            RPC parameters with keys:
            - entity_type (str): Type of entity
            - data (dict): Entity metadata
            - content (str, optional): Markdown content

        Returns
        -------
        dict
            Entity data with keys: id, entity_type, metadata, content, path

        Example RPC call:
            method: "vault.create"
            params: {
                "entity_type": "task",
                "data": {"title": "New Task"},
                "content": "Task description"
            }
        """
        entity_type = params.get("entity_type")
        data = params.get("data", {})
        content = params.get("content", "")

        if not entity_type:
            raise ValueError("entity_type is required")

        entity = self.host_api.create_entity(entity_type, data, content=content)

        return {
            "id": entity.id,
            "entity_type": entity.entity_type,
            "metadata": entity.metadata,
            "content": entity.content,
            "path": str(entity.path) if entity.path else None,
        }

    def handle_vault_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle vault.read RPC call.

        Parameters
        ----------
        params
            RPC parameters with key:
            - entity_id (str): Entity identifier

        Returns
        -------
        dict
            Entity data

        Example RPC call:
            method: "vault.read"
            params: {"entity_id": "task-20250107-1234-example"}
        """
        entity_id = params.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id is required")

        entity = self.host_api.read_entity(entity_id)

        return {
            "id": entity.id,
            "entity_type": entity.entity_type,
            "metadata": entity.metadata,
            "content": entity.content,
            "path": str(entity.path) if entity.path else None,
        }

    def handle_vault_update(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle vault.update RPC call.

        Parameters
        ----------
        params
            RPC parameters with keys:
            - entity_id (str): Entity identifier
            - updates (dict): Metadata updates
            - content (str, optional): New content

        Returns
        -------
        dict
            Updated entity data

        Example RPC call:
            method: "vault.update"
            params: {
                "entity_id": "task-123",
                "updates": {"status": "done"},
                "content": "Completed"
            }
        """
        entity_id = params.get("entity_id")
        updates = params.get("updates", {})
        content = params.get("content")

        if not entity_id:
            raise ValueError("entity_id is required")

        entity = self.host_api.update_entity(entity_id, updates, content=content)

        return {
            "id": entity.id,
            "entity_type": entity.entity_type,
            "metadata": entity.metadata,
            "content": entity.content,
            "path": str(entity.path) if entity.path else None,
        }

    def handle_vault_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle vault.delete RPC call.

        Parameters
        ----------
        params
            RPC parameters with key:
            - entity_id (str): Entity identifier

        Returns
        -------
        dict
            Success confirmation

        Example RPC call:
            method: "vault.delete"
            params: {"entity_id": "task-123"}
        """
        entity_id = params.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id is required")

        self.host_api.delete_entity(entity_id)

        return {"success": True, "entity_id": entity_id}

    def handle_vault_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle vault.list RPC call.

        Parameters
        ----------
        params
            RPC parameters with keys:
            - entity_type (str, optional): Filter by type
            - limit (int, optional): Maximum results
            - offset (int, optional): Skip first N results

        Returns
        -------
        dict
            List of entities and pagination info

        Example RPC call:
            method: "vault.list"
            params: {"entity_type": "task", "limit": 10}
        """
        entity_type = params.get("entity_type")
        limit = params.get("limit")
        offset = params.get("offset", 0)

        entities = list(self.host_api.list_entities(entity_type, limit=limit, offset=offset))

        return {
            "entities": [
                {
                    "id": e.id,
                    "entity_type": e.entity_type,
                    "metadata": e.metadata,
                    "content": e.content,
                    "path": str(e.path) if e.path else None,
                }
                for e in entities
            ],
            "count": len(entities),
            "offset": offset,
        }

    def handle_vault_upsert(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle vault.upsert RPC call.

        Parameters
        ----------
        params
            RPC parameters with keys:
            - entity_type (str): Type of entity
            - data (dict): Entity metadata (include 'id' for update)
            - content (str, optional): Markdown content

        Returns
        -------
        dict
            Created or updated entity data

        Example RPC call:
            method: "vault.upsert"
            params: {
                "entity_type": "task",
                "data": {"id": "task-123", "title": "Updated"},
                "content": "New content"
            }
        """
        entity_type = params.get("entity_type")
        data = params.get("data", {})
        content = params.get("content", "")

        if not entity_type:
            raise ValueError("entity_type is required")

        entity = self.host_api.upsert_entity(entity_type, data, content=content)

        return {
            "id": entity.id,
            "entity_type": entity.entity_type,
            "metadata": entity.metadata,
            "content": entity.content,
            "path": str(entity.path) if entity.path else None,
        }

    def handle_vault_get_links(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle vault.get_links RPC call.

        Parameters
        ----------
        params
            RPC parameters with key:
            - entity_id (str): Entity identifier

        Returns
        -------
        dict
            Links data with incoming and outgoing

        Example RPC call:
            method: "vault.get_links"
            params: {"entity_id": "task-123"}
        """
        entity_id = params.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id is required")

        return self.host_api.get_entity_links(entity_id)

    def handle_vault_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle vault.search RPC call.

        Parameters
        ----------
        params
            RPC parameters with keys:
            - query (str): Search query
            - entity_type (str, optional): Filter by type
            - limit (int, optional): Maximum results

        Returns
        -------
        dict
            Search results

        Example RPC call:
            method: "vault.search"
            params: {"query": "urgent", "entity_type": "task"}
        """
        query = params.get("query", "")
        entity_type = params.get("entity_type")
        limit = params.get("limit", 50)

        if not query:
            return {"entities": [], "count": 0}

        # Simple search implementation
        results = []
        query_lower = query.lower()

        for entity in self.host_api.list_entities(entity_type):
            title = entity.metadata.get("title", "").lower()
            content_lower = entity.content.lower()

            if query_lower in title or query_lower in content_lower:
                results.append(
                    {
                        "id": entity.id,
                        "entity_type": entity.entity_type,
                        "metadata": entity.metadata,
                        "content": entity.content,
                        "path": str(entity.path) if entity.path else None,
                    }
                )

            if len(results) >= limit:
                break

        return {
            "entities": results,
            "count": len(results),
        }


def register_vault_rpc_handlers(host_api: HostAPI) -> dict[str, Any]:
    """Register Vault RPC handlers and return method dispatch table.

    Parameters
    ----------
    host_api
        Host API instance

    Returns
    -------
    dict
        Dictionary mapping RPC method names to handler functions

    Example:
        >>> from kira.core.host import create_host_api
        >>> from kira.core.vault_rpc_handlers import register_vault_rpc_handlers
        >>> host_api = create_host_api(Path("vault"))
        >>> handlers = register_vault_rpc_handlers(host_api)
        >>> result = handlers["vault.create"]({"entity_type": "task", "data": {"title": "Test"}})
    """
    vault_rpc = VaultRPCHandlers(host_api)

    return {
        "vault.create": vault_rpc.handle_vault_create,
        "vault.read": vault_rpc.handle_vault_read,
        "vault.update": vault_rpc.handle_vault_update,
        "vault.delete": vault_rpc.handle_vault_delete,
        "vault.list": vault_rpc.handle_vault_list,
        "vault.upsert": vault_rpc.handle_vault_upsert,
        "vault.get_links": vault_rpc.handle_vault_get_links,
        "vault.search": vault_rpc.handle_vault_search,
    }
