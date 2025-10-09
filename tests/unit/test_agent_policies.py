"""Unit tests for Sprint 3 policy and security features."""

import json
from pathlib import Path

import pytest

from kira.agent.policies import Capability, PolicyEnforcer, PolicyViolation, ToolPolicy


class TestCapability:
    """Tests for Capability enum."""

    def test_capability_values(self):
        """Test capability enum values."""
        assert Capability.READ.value == "read"
        assert Capability.CREATE.value == "create"
        assert Capability.UPDATE.value == "update"
        assert Capability.DELETE.value == "delete"
        assert Capability.EXPORT.value == "export"


class TestToolPolicy:
    """Tests for ToolPolicy."""

    def test_tool_policy_creation(self):
        """Test creating a tool policy."""
        policy = ToolPolicy(
            tool_name="task_create",
            required_capabilities=[Capability.CREATE],
            destructive=False,
        )

        assert policy.tool_name == "task_create"
        assert Capability.CREATE in policy.required_capabilities
        assert not policy.destructive

    def test_requires_confirmation(self):
        """Test confirmation requirement."""
        safe_policy = ToolPolicy(
            tool_name="task_list",
            required_capabilities=[Capability.READ],
            destructive=False,
        )
        destructive_policy = ToolPolicy(
            tool_name="task_delete",
            required_capabilities=[Capability.DELETE],
            destructive=True,
        )

        assert not safe_policy.requires_confirmation()
        assert destructive_policy.requires_confirmation()

    def test_is_allowed_with_capabilities(self):
        """Test capability check."""
        policy = ToolPolicy(
            tool_name="task_create",
            required_capabilities=[Capability.CREATE],
        )

        assert policy.is_allowed({Capability.CREATE, Capability.READ})
        assert not policy.is_allowed({Capability.READ})

    def test_blocked_tool(self):
        """Test explicitly blocked tool."""
        policy = ToolPolicy(
            tool_name="task_delete",
            required_capabilities=[Capability.DELETE],
            allowed=False,
        )

        assert not policy.is_allowed({Capability.DELETE})


class TestPolicyEnforcer:
    """Tests for PolicyEnforcer."""

    def test_default_capabilities(self):
        """Test default capabilities when creating enforcer."""
        enforcer = PolicyEnforcer()

        assert Capability.READ in enforcer.available_capabilities
        assert Capability.CREATE in enforcer.available_capabilities
        assert Capability.UPDATE in enforcer.available_capabilities
        assert Capability.EXPORT in enforcer.available_capabilities
        # DELETE is not default
        assert Capability.DELETE not in enforcer.available_capabilities

    def test_check_policy_allowed(self):
        """Test policy check for allowed operation."""
        enforcer = PolicyEnforcer()

        # Should not raise - task_list requires READ, which is available by default
        enforcer.check_policy("task_list", {})

    def test_check_policy_denied_missing_capability(self):
        """Test policy check for denied operation due to missing capability."""
        enforcer = PolicyEnforcer()

        # task_delete requires DELETE capability, which is not available by default
        with pytest.raises(PolicyViolation) as exc_info:
            enforcer.check_policy("task_delete", {})

        assert "capabilities" in str(exc_info.value).lower()

    def test_check_policy_denied_not_in_allowlist(self):
        """Test policy check for tool not in allowlist."""
        enforcer = PolicyEnforcer()

        with pytest.raises(PolicyViolation) as exc_info:
            enforcer.check_policy("unknown_tool", {})

        assert "allowlist" in str(exc_info.value).lower()

    def test_check_policy_requires_confirmation(self):
        """Test policy check with confirmation requirement."""
        enforcer = PolicyEnforcer()
        enforcer.add_capability(Capability.DELETE)

        # Without confirmation
        with pytest.raises(PolicyViolation) as exc_info:
            enforcer.check_policy("task_delete", {}, has_confirmation=False)

        assert "confirmation" in str(exc_info.value).lower()

        # With confirmation
        enforcer.check_policy("task_delete", {}, has_confirmation=True)

    def test_is_tool_allowed(self):
        """Test basic tool allowlist check."""
        enforcer = PolicyEnforcer()

        assert enforcer.is_tool_allowed("task_list")
        assert enforcer.is_tool_allowed("task_create")
        assert not enforcer.is_tool_allowed("task_delete")  # Requires DELETE capability
        assert not enforcer.is_tool_allowed("unknown_tool")

    def test_get_allowed_tools(self):
        """Test getting list of allowed tools."""
        enforcer = PolicyEnforcer()

        allowed = enforcer.get_allowed_tools()

        assert "task_list" in allowed
        assert "task_create" in allowed
        assert "task_delete" not in allowed

    def test_add_remove_capability(self):
        """Test adding and removing capabilities."""
        enforcer = PolicyEnforcer()

        # Initially DELETE is not available
        assert Capability.DELETE not in enforcer.available_capabilities

        # Add DELETE
        enforcer.add_capability(Capability.DELETE)
        assert Capability.DELETE in enforcer.available_capabilities
        assert enforcer.is_tool_allowed("task_delete")

        # Remove DELETE
        enforcer.remove_capability(Capability.DELETE)
        assert Capability.DELETE not in enforcer.available_capabilities
        assert not enforcer.is_tool_allowed("task_delete")

    def test_set_custom_tool_policy(self):
        """Test setting custom tool policy."""
        enforcer = PolicyEnforcer()

        # Add custom tool policy
        custom_policy = ToolPolicy(
            tool_name="custom_tool",
            required_capabilities=[Capability.READ],
            destructive=False,
        )
        enforcer.set_tool_policy(custom_policy)

        # Now custom_tool should be allowed
        assert enforcer.is_tool_allowed("custom_tool")


class TestPolicyEnforcerFactory:
    """Tests for create_policy_enforcer factory function."""

    def test_create_with_default_settings(self):
        """Test creating enforcer with default settings."""
        from kira.agent.policies import create_policy_enforcer

        enforcer = create_policy_enforcer()

        assert Capability.READ in enforcer.available_capabilities
        assert Capability.CREATE in enforcer.available_capabilities
        assert Capability.DELETE not in enforcer.available_capabilities

    def test_create_with_delete_enabled(self):
        """Test creating enforcer with DELETE capability."""
        from kira.agent.policies import create_policy_enforcer

        enforcer = create_policy_enforcer(enable_delete=True)

        assert Capability.DELETE in enforcer.available_capabilities

    def test_create_with_custom_policies(self):
        """Test creating enforcer with custom policies."""
        from kira.agent.policies import create_policy_enforcer

        custom_policy = ToolPolicy(
            tool_name="my_custom_tool",
            required_capabilities=[Capability.READ],
        )

        enforcer = create_policy_enforcer(custom_policies={"my_custom_tool": custom_policy})

        assert enforcer.is_tool_allowed("my_custom_tool")
