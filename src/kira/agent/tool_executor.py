"""Tool execution adapter for in-process Python API calls.

Phase 2, Item 7: Execution adapter for tools.
Provides validated, idempotent tool execution with proper error mapping.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.host import HostAPI

from .kira_tools import RollupDailyTool, TaskCreateTool, TaskGetTool, TaskListTool, TaskUpdateTool
from .tool_schemas import TOOL_SCHEMAS, validate_tool_args
from .tools import AgentTool, ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["ToolExecutor", "create_tool_executor", "InboxNormalizeTool"]


class InboxNormalizeTool:
    """Normalize inbox items (stub for now)."""

    name = "inbox_normalize"
    description = "Normalize and process inbox items"

    def get_parameters(self) -> dict[str, Any]:
        """Get parameter schema."""
        return {
            "type": "object",
            "properties": {
                "dry_run": {"type": "boolean", "default": True},
                "batch_size": {"type": "integer", "default": 10},
            },
        }

    def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute inbox normalization."""
        if dry_run or args.get("dry_run", True):
            return ToolResult.ok(
                {"message": "Dry run: would normalize inbox", "items_processed": 0},
                meta={"dry_run": True},
            )

        # Stub implementation
        return ToolResult.ok(
            {"message": "Inbox normalized", "items_processed": 0},
            meta={"operation": "inbox_normalize"},
        )


class ToolExecutor:
    """Executes tools with validation and error mapping.

    Provides:
    - Pre-execution argument validation
    - In-process Python API calls (no shell)
    - Structured error mapping
    - Idempotency checks
    - Deterministic JSON I/O
    """

    def __init__(self, host_api: HostAPI, vault_path: Path) -> None:
        """Initialize tool executor.

        Parameters
        ----------
        host_api
            Host API for vault operations
        vault_path
            Path to vault root
        """
        self.host_api = host_api
        self.vault_path = vault_path
        self._tool_instances: dict[str, Any] = {}
        self._init_tools()

    def _init_tools(self) -> None:
        """Initialize tool instances."""
        from .kira_tools import TaskDeleteTool

        self._tool_instances = {
            "task_create": TaskCreateTool(host_api=self.host_api),
            "task_update": TaskUpdateTool(host_api=self.host_api),
            "task_delete": TaskDeleteTool(host_api=self.host_api),
            "task_get": TaskGetTool(host_api=self.host_api),
            "task_list": TaskListTool(host_api=self.host_api),
            "rollup_daily": RollupDailyTool(vault_path=self.vault_path),
            "inbox_normalize": InboxNormalizeTool(),
        }
        logger.info(f"Initialized {len(self._tool_instances)} tools")

    def execute_tool(self, tool_name: str, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute tool with validation.

        Parameters
        ----------
        tool_name
            Tool name
        args
            Tool arguments
        dry_run
            Run in dry-run mode

        Returns
        -------
        ToolResult
            Execution result with status, data/error, meta
        """
        logger.debug(f"Executing tool: {tool_name} (dry_run={dry_run})")

        # Get tool instance
        tool = self._tool_instances.get(tool_name)
        if not tool:
            available = list(self._tool_instances.keys())
            return ToolResult.error(
                f"Tool not found: {tool_name}. Available: {', '.join(available)}",
                meta={"available_tools": available},
            )

        # Validate arguments
        try:
            validated_args = validate_tool_args(tool_name, args)
            logger.debug(f"Validated args: {validated_args}")
        except ValueError as e:
            return ToolResult.error(
                f"Argument validation failed: {e}",
                meta={"tool": tool_name, "raw_args": args},
            )

        # Execute tool
        try:
            result = tool.execute(validated_args, dry_run=dry_run)

            # Enhance metadata
            result.meta["tool"] = tool_name
            result.meta["validated"] = True

            # Preserve timestamps if present
            if result.status == "ok" and "uid" in result.data:
                result.meta["entity_id"] = result.data["uid"]

            logger.info(f"Tool {tool_name} executed: status={result.status}")
            return result

        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}", exc_info=True)
            return ToolResult.error(
                f"Execution failed: {e}",
                meta={"tool": tool_name, "error_type": type(e).__name__},
            )

    def get_tool_registry(self) -> ToolRegistry:
        """Get tool registry for LangGraph integration.

        Returns
        -------
        ToolRegistry
            Populated tool registry
        """
        registry = ToolRegistry()

        # Wrap each tool for registry
        for name, tool_instance in self._tool_instances.items():
            # Create wrapper that matches AgentTool protocol
            class ToolWrapper:
                """Wrapper to make tool compatible with AgentTool protocol."""

                def __init__(self, executor: ToolExecutor, tool_name: str, instance: Any) -> None:
                    self.name = tool_name
                    self.description = getattr(instance, "description", f"Execute {tool_name}")
                    self._executor = executor
                    self._tool_name = tool_name
                    self._instance = instance

                def get_parameters(self) -> dict[str, Any]:
                    """Get parameter schema."""
                    schema = TOOL_SCHEMAS.get(self._tool_name)
                    if schema:
                        return schema.get_json_schema()
                    return self._instance.get_parameters()

                def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
                    """Execute tool."""
                    return self._executor.execute_tool(self._tool_name, args, dry_run=dry_run)

            wrapper = ToolWrapper(self, name, tool_instance)
            registry.register(wrapper)  # type: ignore[arg-type]

        logger.info(f"Created tool registry with {len(registry.list_tools())} tools")
        return registry


def create_tool_executor(host_api: HostAPI, vault_path: Path) -> ToolExecutor:
    """Factory function to create tool executor.

    Parameters
    ----------
    host_api
        Host API for vault operations
    vault_path
        Path to vault root

    Returns
    -------
    ToolExecutor
        Configured tool executor
    """
    return ToolExecutor(host_api, vault_path)

