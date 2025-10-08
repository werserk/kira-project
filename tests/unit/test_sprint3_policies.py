"""Unit tests for Sprint 3 policy and security features."""

import json
from pathlib import Path

import pytest

from kira.agent.policies import TOOL_CAPABILITIES, AgentPolicy, Capability, PolicyManager, PolicyViolationError


class TestCapability:
    """Tests for Capability enum."""

    def test_capability_values(self):
        """Test capability enum values."""
        assert Capability.READ.value == "read"
        assert Capability.CREATE.value == "create"
        assert Capability.UPDATE.value == "update"
        assert Capability.DELETE.value == "delete"
        assert Capability.EXPORT.value == "export"


class TestAgentPolicy:
    """Tests for AgentPolicy."""

    def test_can_execute_with_capability(self):
        """Test capability check."""
        policy = AgentPolicy(
            allowed_capabilities={Capability.READ, Capability.CREATE}
        )

        assert policy.can_execute("task_list", Capability.READ)
        assert policy.can_execute("task_create", Capability.CREATE)
        assert not policy.can_execute("task_delete", Capability.DELETE)

    def test_tool_whitelist(self):
        """Test tool whitelist."""
        policy = AgentPolicy(
            allowed_capabilities={Capability.READ},
            allowed_tools={"task_list", "task_get"},
        )

        assert policy.can_execute("task_list", Capability.READ)
        assert not policy.can_execute("rollup_daily", Capability.READ)

    def test_requires_confirmation(self):
        """Test confirmation requirement."""
        policy = AgentPolicy(
            allowed_capabilities={Capability.DELETE},
            require_confirmation={"task_delete"},
        )

        assert policy.requires_confirmation("task_delete")
        assert not policy.requires_confirmation("task_list")

    def test_from_dict(self):
        """Test loading policy from dict."""
        data = {
            "allowed_capabilities": ["read", "create"],
            "allowed_tools": ["task_list", "task_create"],
            "require_confirmation": ["task_delete"],
            "max_tool_calls_per_request": 5,
        }

        policy = AgentPolicy.from_dict(data)

        assert Capability.READ in policy.allowed_capabilities
        assert Capability.CREATE in policy.allowed_capabilities
        assert "task_list" in policy.allowed_tools
        assert policy.max_tool_calls_per_request == 5

    def test_to_dict(self):
        """Test converting policy to dict."""
        policy = AgentPolicy(
            allowed_capabilities={Capability.READ},
            allowed_tools={"task_list"},
            require_confirmation={"task_delete"},
        )

        data = policy.to_dict()

        assert "read" in data["allowed_capabilities"]
        assert "task_list" in data["allowed_tools"]
        assert "task_delete" in data["require_confirmation"]


class TestPolicyManager:
    """Tests for PolicyManager."""

    def test_default_policy(self):
        """Test default policy when no file exists."""
        manager = PolicyManager(policy_path=None)

        assert Capability.READ in manager.policy.allowed_capabilities
        assert Capability.CREATE in manager.policy.allowed_capabilities

    def test_load_policy_from_file(self, tmp_path):
        """Test loading policy from file."""
        policy_file = tmp_path / "policy.json"
        policy_data = {
            "allowed_capabilities": ["read"],
            "allowed_tools": None,
            "require_confirmation": [],
            "max_tool_calls_per_request": 10,
        }

        with policy_file.open("w") as f:
            json.dump(policy_data, f)

        manager = PolicyManager(policy_path=policy_file)

        assert Capability.READ in manager.policy.allowed_capabilities
        assert Capability.CREATE not in manager.policy.allowed_capabilities

    def test_save_policy(self, tmp_path):
        """Test saving policy to file."""
        policy_file = tmp_path / "policy.json"

        manager = PolicyManager(policy_path=policy_file)
        manager.policy.allowed_capabilities = {Capability.READ}
        manager.save_policy()

        assert policy_file.exists()

        # Verify saved content
        with policy_file.open() as f:
            data = json.load(f)
            assert "read" in data["allowed_capabilities"]

    def test_check_permission_allowed(self):
        """Test permission check for allowed operation."""
        manager = PolicyManager()
        manager.policy = AgentPolicy(
            allowed_capabilities={Capability.READ}
        )

        # Should not raise
        manager.check_permission("task_list", Capability.READ)

    def test_check_permission_denied(self):
        """Test permission check for denied operation."""
        manager = PolicyManager()
        manager.policy = AgentPolicy(
            allowed_capabilities={Capability.READ}
        )

        with pytest.raises(PolicyViolationError) as exc_info:
            manager.check_permission("task_delete", Capability.DELETE)

        assert "not allowed" in str(exc_info.value)
        assert exc_info.value.capability == "delete"
        assert exc_info.value.tool == "task_delete"

    def test_check_permission_requires_confirmation(self):
        """Test permission check with confirmation requirement."""
        manager = PolicyManager()
        manager.policy = AgentPolicy(
            allowed_capabilities={Capability.DELETE},
            require_confirmation={"task_delete"},
        )

        # Without confirmation
        with pytest.raises(PolicyViolationError) as exc_info:
            manager.check_permission("task_delete", Capability.DELETE, confirmed=False)

        assert "confirmation" in str(exc_info.value)

        # With confirmation
        manager.check_permission("task_delete", Capability.DELETE, confirmed=True)


class TestToolCapabilities:
    """Tests for tool capability mapping."""

    def test_tool_capabilities_defined(self):
        """Test that common tools have capabilities defined."""
        assert TOOL_CAPABILITIES["task_create"] == Capability.CREATE
        assert TOOL_CAPABILITIES["task_update"] == Capability.UPDATE
        assert TOOL_CAPABILITIES["task_delete"] == Capability.DELETE
        assert TOOL_CAPABILITIES["task_get"] == Capability.READ
        assert TOOL_CAPABILITIES["task_list"] == Capability.READ
