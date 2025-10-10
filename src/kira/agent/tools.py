"""Tool registry and base tool interface for agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

__all__ = [
    "AgentTool",
    "ToolRegistry",
    "ToolResult",
    "ToolError",
]


class ToolError(Exception):
    """Base exception for tool errors."""

    pass


@dataclass
class ToolResult:
    """Result from tool execution."""

    status: str  # "ok" or "error"
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"status": self.status}
        if self.status == "ok":
            result["data"] = self.data
        else:
            result["error"] = self.error
        if self.meta:
            result["meta"] = self.meta
        return result

    @classmethod
    def ok(cls, data: dict[str, Any], meta: dict[str, Any] | None = None) -> ToolResult:
        """Create success result."""
        return cls(status="ok", data=data, meta=meta or {})

    @classmethod
    def error(cls, error_msg: str, meta: dict[str, Any] | None = None) -> ToolResult:
        """Create error result."""
        return cls(status="error", error=error_msg, meta=meta or {})


class AgentTool(Protocol):
    """Protocol for agent tools."""

    name: str
    description: str

    def get_parameters(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters.

        Returns
        -------
        dict
            JSON schema describing tool parameters
        """
        ...

    def execute(self, args: dict[str, Any], *, dry_run: bool = False) -> ToolResult:
        """Execute tool with given arguments.

        Parameters
        ----------
        args
            Tool arguments
        dry_run
            If True, don't make actual changes

        Returns
        -------
        ToolResult
            Execution result
        """
        ...


class ToolRegistry:
    """Registry for agent tools."""

    def __init__(self) -> None:
        """Initialize tool registry."""
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        """Register a tool.

        Parameters
        ----------
        tool
            Tool to register
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool | None:
        """Get tool by name.

        Parameters
        ----------
        name
            Tool name

        Returns
        -------
        AgentTool | None
            Tool or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[AgentTool]:
        """List all registered tools.

        Returns
        -------
        list[AgentTool]
            List of tools
        """
        return list(self._tools.values())

    def get_tools_description(self) -> str:
        """Get formatted description of all tools.

        Returns
        -------
        str
            Tools description for prompt
        """
        descriptions = []
        for tool in self._tools.values():
            params = tool.get_parameters()
            descriptions.append(f"- {tool.name}: {tool.description}")
            descriptions.append(f"  Parameters: {params}")
        return "\n".join(descriptions)

    def to_api_format(self) -> list[Any]:
        """Convert tools to LLM API format (Tool objects).

        This method converts our internal tool representation to the format
        expected by LLM adapters' tool_call() API.

        Returns
        -------
        list[Tool]
            List of Tool objects for LLM API
        """
        from ..adapters.llm import Tool

        api_tools = []
        for tool in self._tools.values():
            api_tools.append(
                Tool(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.get_parameters()
                )
            )
        return api_tools
