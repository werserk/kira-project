"""Capability policies for agent tool execution.

Phase 3, Item 11: Capabilities & policy enforcement.
Enforces read/create/update/delete/export permissions at tool_node boundary.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Capability", "ToolPolicy", "PolicyEnforcer", "PolicyViolation", "create_policy_enforcer"]


class Capability(str, Enum):
    """Tool capability types."""

    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"


class PolicyViolation(Exception):
    """Raised when a policy is violated."""

    pass


@dataclass
class ToolPolicy:
    """Policy for a single tool."""

    tool_name: str
    required_capabilities: list[Capability]
    destructive: bool = False  # Requires confirmation
    allowed: bool = True  # Can be blocked entirely
    read_only: bool = False  # Read operations only
    metadata: dict[str, Any] = field(default_factory=dict)

    def requires_confirmation(self) -> bool:
        """Check if tool requires confirmation."""
        return self.destructive

    def is_allowed(self, capabilities: set[Capability]) -> bool:
        """Check if tool is allowed with given capabilities.

        Parameters
        ----------
        capabilities
            Set of available capabilities

        Returns
        -------
        bool
            True if all required capabilities are present
        """
        if not self.allowed:
            return False

        required = set(self.required_capabilities)
        return required.issubset(capabilities)


class PolicyEnforcer:
    """Enforces capability policies for tool execution.

    Checks:
    - Tool is in allowlist
    - User has required capabilities
    - Destructive operations have confirmation
    - No policy violations
    """

    def __init__(
        self,
        policies: dict[str, ToolPolicy] | None = None,
        available_capabilities: set[Capability] | None = None,
        require_confirmation_for_destructive: bool = True,
    ) -> None:
        """Initialize policy enforcer.

        Parameters
        ----------
        policies
            Tool policies (tool_name -> ToolPolicy)
        available_capabilities
            Set of capabilities available to agent
        require_confirmation_for_destructive
            If True, destructive operations require explicit confirmation
        """
        self.policies = policies or self._get_default_policies()
        self.available_capabilities = available_capabilities or self._get_default_capabilities()
        self.require_confirmation_for_destructive = require_confirmation_for_destructive

    def _get_default_policies(self) -> dict[str, ToolPolicy]:
        """Get default tool policies.

        Returns
        -------
        dict
            Default policies for all tools
        """
        return {
            "task_create": ToolPolicy(
                tool_name="task_create",
                required_capabilities=[Capability.CREATE],
                destructive=False,
            ),
            "task_update": ToolPolicy(
                tool_name="task_update",
                required_capabilities=[Capability.UPDATE],
                destructive=False,
            ),
            "task_get": ToolPolicy(
                tool_name="task_get",
                required_capabilities=[Capability.READ],
                read_only=True,
            ),
            "task_list": ToolPolicy(
                tool_name="task_list",
                required_capabilities=[Capability.READ],
                read_only=True,
            ),
            "task_delete": ToolPolicy(
                tool_name="task_delete",
                required_capabilities=[Capability.DELETE],
                destructive=True,
            ),
            "rollup_daily": ToolPolicy(
                tool_name="rollup_daily",
                required_capabilities=[Capability.CREATE, Capability.EXPORT],
                destructive=False,
            ),
            "inbox_normalize": ToolPolicy(
                tool_name="inbox_normalize",
                required_capabilities=[Capability.UPDATE],
                destructive=False,
            ),
        }

    def _get_default_capabilities(self) -> set[Capability]:
        """Get default capabilities (all except delete).

        Returns
        -------
        set
            Default capability set
        """
        return {
            Capability.READ,
            Capability.CREATE,
            Capability.UPDATE,
            Capability.EXPORT,
        }

    def check_policy(
        self,
        tool_name: str,
        args: dict[str, Any],
        *,
        has_confirmation: bool = False,
    ) -> None:
        """Check if tool execution is allowed by policy.

        Parameters
        ----------
        tool_name
            Tool name
        args
            Tool arguments
        has_confirmation
            Whether user has provided confirmation for destructive ops

        Raises
        ------
        PolicyViolation
            If policy check fails
        """
        # Check if tool is in policy list
        if tool_name not in self.policies:
            logger.warning(f"Tool '{tool_name}' not in policy list, denying by default")
            raise PolicyViolation(f"Tool not in allowlist: {tool_name}")

        policy = self.policies[tool_name]

        # Check if tool is allowed at all
        if not policy.allowed:
            logger.warning(f"Tool '{tool_name}' is explicitly blocked")
            raise PolicyViolation(f"Tool is blocked: {tool_name}")

        # Check capabilities
        if not policy.is_allowed(self.available_capabilities):
            missing = set(policy.required_capabilities) - self.available_capabilities
            logger.warning(f"Missing capabilities for '{tool_name}': {missing}")
            raise PolicyViolation(
                f"Insufficient capabilities for {tool_name}. Missing: {', '.join(c.value for c in missing)}"
            )

        # Check confirmation for destructive operations
        if (
            self.require_confirmation_for_destructive
            and policy.requires_confirmation()
            and not has_confirmation
        ):
            logger.warning(f"Destructive operation '{tool_name}' requires confirmation")
            raise PolicyViolation(f"Destructive operation requires confirmation: {tool_name}")

        logger.debug(f"Policy check passed for tool '{tool_name}'")

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if tool is allowed (basic check).

        Parameters
        ----------
        tool_name
            Tool name

        Returns
        -------
        bool
            True if tool is in allowlist and not blocked
        """
        if tool_name not in self.policies:
            return False

        policy = self.policies[tool_name]
        return policy.allowed and policy.is_allowed(self.available_capabilities)

    def get_allowed_tools(self) -> list[str]:
        """Get list of allowed tool names.

        Returns
        -------
        list[str]
            List of allowed tool names
        """
        return [name for name in self.policies if self.is_tool_allowed(name)]

    def add_capability(self, capability: Capability) -> None:
        """Add a capability to available set.

        Parameters
        ----------
        capability
            Capability to add
        """
        self.available_capabilities.add(capability)
        logger.info(f"Added capability: {capability.value}")

    def remove_capability(self, capability: Capability) -> None:
        """Remove a capability from available set.

        Parameters
        ----------
        capability
            Capability to remove
        """
        self.available_capabilities.discard(capability)
        logger.info(f"Removed capability: {capability.value}")

    def set_tool_policy(self, policy: ToolPolicy) -> None:
        """Set or update policy for a tool.

        Parameters
        ----------
        policy
            Tool policy
        """
        self.policies[policy.tool_name] = policy
        logger.info(f"Updated policy for tool: {policy.tool_name}")


def create_policy_enforcer(
    *,
    enable_delete: bool = False,
    require_confirmation: bool = True,
    custom_policies: dict[str, ToolPolicy] | None = None,
) -> PolicyEnforcer:
    """Factory function to create policy enforcer.

    Parameters
    ----------
    enable_delete
        Enable DELETE capability
    require_confirmation
        Require confirmation for destructive operations
    custom_policies
        Custom tool policies to merge with defaults

    Returns
    -------
    PolicyEnforcer
        Configured policy enforcer
    """
    capabilities = {
        Capability.READ,
        Capability.CREATE,
        Capability.UPDATE,
        Capability.EXPORT,
    }

    if enable_delete:
        capabilities.add(Capability.DELETE)

    enforcer = PolicyEnforcer(
        available_capabilities=capabilities,
        require_confirmation_for_destructive=require_confirmation,
    )

    # Merge custom policies
    if custom_policies:
        for policy in custom_policies.values():
            enforcer.set_tool_policy(policy)

    logger.info(f"Created policy enforcer with capabilities: {[c.value for c in capabilities]}")
    return enforcer
