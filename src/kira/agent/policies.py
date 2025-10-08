"""Capability-based access control for agent operations.

Enforces security policies at tool execution boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = [
    "Capability",
    "AgentPolicy",
    "PolicyViolationError",
    "PolicyManager",
]


class Capability(Enum):
    """Agent capabilities."""

    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"


class PolicyViolationError(Exception):
    """Raised when policy is violated."""

    def __init__(self, message: str, *, capability: str, tool: str) -> None:
        """Initialize error.

        Parameters
        ----------
        message
            Error message
        capability
            Required capability
        tool
            Tool that was blocked
        """
        super().__init__(message)
        self.capability = capability
        self.tool = tool


@dataclass
class AgentPolicy:
    """Agent security policy."""

    allowed_capabilities: set[Capability]
    allowed_tools: set[str] | None = None  # None = all tools
    require_confirmation: set[str] | None = None  # Tools requiring confirmation
    max_tool_calls_per_request: int = 10

    def can_execute(self, tool: str, capability: Capability) -> bool:
        """Check if tool can be executed with capability.

        Parameters
        ----------
        tool
            Tool name
        capability
            Required capability

        Returns
        -------
        bool
            True if allowed
        """
        # Check capability
        if capability not in self.allowed_capabilities:
            return False

        # Check tool whitelist
        if self.allowed_tools is not None and tool not in self.allowed_tools:
            return False

        return True

    def requires_confirmation(self, tool: str) -> bool:
        """Check if tool requires confirmation.

        Parameters
        ----------
        tool
            Tool name

        Returns
        -------
        bool
            True if confirmation required
        """
        if self.require_confirmation is None:
            return False
        return tool in self.require_confirmation

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPolicy:
        """Load policy from dictionary.

        Parameters
        ----------
        data
            Policy data

        Returns
        -------
        AgentPolicy
            Loaded policy
        """
        capabilities = {Capability(c) for c in data.get("allowed_capabilities", [])}

        allowed_tools = data.get("allowed_tools")
        if allowed_tools is not None:
            allowed_tools = set(allowed_tools)

        require_confirmation = data.get("require_confirmation")
        if require_confirmation is not None:
            require_confirmation = set(require_confirmation)

        return cls(
            allowed_capabilities=capabilities,
            allowed_tools=allowed_tools,
            require_confirmation=require_confirmation,
            max_tool_calls_per_request=data.get("max_tool_calls_per_request", 10),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert policy to dictionary.

        Returns
        -------
        dict
            Policy data
        """
        return {
            "allowed_capabilities": [c.value for c in self.allowed_capabilities],
            "allowed_tools": list(self.allowed_tools) if self.allowed_tools else None,
            "require_confirmation": list(self.require_confirmation) if self.require_confirmation else None,
            "max_tool_calls_per_request": self.max_tool_calls_per_request,
        }


class PolicyManager:
    """Manages agent policies."""

    def __init__(self, policy_path: Path | None = None) -> None:
        """Initialize policy manager.

        Parameters
        ----------
        policy_path
            Path to policy file
        """
        self.policy_path = policy_path
        self.policy = self._load_policy()

    def _load_policy(self) -> AgentPolicy:
        """Load policy from file or use default.

        Returns
        -------
        AgentPolicy
            Loaded policy
        """
        if self.policy_path and self.policy_path.exists():
            try:
                with self.policy_path.open() as f:
                    data = json.load(f)
                    return AgentPolicy.from_dict(data)
            except Exception:
                # Fall back to default on error
                pass

        # Default policy: allow read and create only
        return AgentPolicy(
            allowed_capabilities={Capability.READ, Capability.CREATE},
            require_confirmation={"task_delete", "vault_export"},
        )

    def save_policy(self) -> None:
        """Save current policy to file."""
        if self.policy_path:
            self.policy_path.parent.mkdir(parents=True, exist_ok=True)
            with self.policy_path.open("w") as f:
                json.dump(self.policy.to_dict(), f, indent=2)

    def check_permission(
        self,
        tool: str,
        capability: Capability,
        *,
        confirmed: bool = False,
    ) -> None:
        """Check if operation is permitted.

        Parameters
        ----------
        tool
            Tool name
        capability
            Required capability
        confirmed
            Whether user confirmed operation

        Raises
        ------
        PolicyViolationError
            If operation not permitted
        """
        if not self.policy.can_execute(tool, capability):
            raise PolicyViolationError(
                f"Tool '{tool}' requires capability '{capability.value}' which is not allowed",
                capability=capability.value,
                tool=tool,
            )

        if self.policy.requires_confirmation(tool) and not confirmed:
            raise PolicyViolationError(
                f"Tool '{tool}' requires explicit confirmation (--yes flag)",
                capability=capability.value,
                tool=tool,
            )


# Tool to capability mapping
TOOL_CAPABILITIES: dict[str, Capability] = {
    "task_create": Capability.CREATE,
    "task_update": Capability.UPDATE,
    "task_delete": Capability.DELETE,
    "task_get": Capability.READ,
    "task_list": Capability.READ,
    "rollup_daily": Capability.READ,
    "vault_export": Capability.EXPORT,
}
