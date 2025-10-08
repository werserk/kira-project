"""Tests for permission enforcement and policy checks (ADR-004)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.policy import (
    PermissionDeniedError,
    Policy,
    PolicyViolation,
    SandboxConfig,
    check_fs_access,
    check_permission,
)


class TestSandboxConfig:
    """Tests for SandboxConfig."""

    def test_from_manifest_default(self):
        """Test creating SandboxConfig with defaults."""
        manifest = {}
        config = SandboxConfig.from_manifest(manifest)

        assert config.strategy == "subprocess"
        assert config.timeout_ms == 30000
        assert config.memory_limit_mb is None
        assert config.network_access is False
        assert config.fs_read_paths == []
        assert config.fs_write_paths == []

    def test_from_manifest_full(self):
        """Test creating SandboxConfig with all options."""
        manifest = {
            "sandbox": {
                "strategy": "subprocess",
                "timeoutMs": 60000,
                "memoryLimit": 256,
                "networkAccess": True,
                "fsAccess": {
                    "read": ["/tmp", "/var/log"],
                    "write": ["/tmp/plugin"],
                },
            }
        }
        config = SandboxConfig.from_manifest(manifest)

        assert config.strategy == "subprocess"
        assert config.timeout_ms == 60000
        assert config.memory_limit_mb == 256
        assert config.network_access is True
        assert config.fs_read_paths == ["/tmp", "/var/log"]
        assert config.fs_write_paths == ["/tmp/plugin"]


class TestPolicy:
    """Tests for Policy permission checking."""

    def test_from_manifest(self):
        """Test creating Policy from manifest."""
        manifest = {
            "name": "test-plugin",
            "permissions": ["net", "vault.read"],
            "sandbox": {"strategy": "subprocess"},
        }
        vault_path = Path("/vault")
        policy = Policy.from_manifest(manifest, vault_path)

        assert policy.plugin_name == "test-plugin"
        assert "net" in policy.granted_permissions
        assert "vault.read" in policy.granted_permissions
        assert policy.vault_path == vault_path

    def test_check_permission_granted(self):
        """Test permission check passes when permission granted."""
        policy = Policy(
            plugin_name="test",
            granted_permissions=["net", "vault.read"],
            sandbox_config=SandboxConfig(),
        )

        # Should not raise
        policy.check_permission("net")
        policy.check_permission("vault.read")

    def test_check_permission_denied(self):
        """Test permission check fails when permission not granted."""
        policy = Policy(
            plugin_name="test",
            granted_permissions=["vault.read"],
            sandbox_config=SandboxConfig(),
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_permission("net")

        assert "net" in str(exc_info.value)
        assert exc_info.value.permission == "net"

    def test_check_network_access_granted(self):
        """Test network access check when allowed."""
        policy = Policy(
            plugin_name="test",
            granted_permissions=["net"],
            sandbox_config=SandboxConfig(network_access=True),
        )

        # Should not raise
        policy.check_network_access()

    def test_check_network_access_no_permission(self):
        """Test network access check fails without permission."""
        policy = Policy(
            plugin_name="test",
            granted_permissions=[],
            sandbox_config=SandboxConfig(network_access=True),
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_network_access()

        assert "net" in str(exc_info.value)

    def test_check_network_access_disabled_sandbox(self):
        """Test network access check fails when sandbox disables it."""
        policy = Policy(
            plugin_name="test",
            granted_permissions=["net"],
            sandbox_config=SandboxConfig(network_access=False),
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_network_access()

        assert "sandbox configuration" in str(exc_info.value)

    def test_check_fs_read_access_granted(self, tmp_path):
        """Test filesystem read access when allowed."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        test_file = allowed_dir / "test.txt"

        policy = Policy(
            plugin_name="test",
            granted_permissions=["fs.read"],
            sandbox_config=SandboxConfig(fs_read_paths=[str(allowed_dir)]),
        )

        # Should not raise
        policy.check_fs_read_access(test_file)

    def test_check_fs_read_access_denied_no_permission(self, tmp_path):
        """Test filesystem read access fails without permission."""
        test_file = tmp_path / "test.txt"

        policy = Policy(
            plugin_name="test",
            granted_permissions=[],
            sandbox_config=SandboxConfig(fs_read_paths=[str(tmp_path)]),
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_fs_read_access(test_file)

        assert "fs.read" in str(exc_info.value)

    def test_check_fs_read_access_denied_not_in_allowlist(self, tmp_path):
        """Test filesystem read access fails when path not in allowlist."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        forbidden_dir.mkdir()
        test_file = forbidden_dir / "test.txt"

        policy = Policy(
            plugin_name="test",
            granted_permissions=["fs.read"],
            sandbox_config=SandboxConfig(fs_read_paths=[str(allowed_dir)]),
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_fs_read_access(test_file)

        assert "not in read allowlist" in str(exc_info.value)

    def test_check_fs_write_access_vault_forbidden(self, tmp_path):
        """Test direct vault writes are forbidden (ADR-006)."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        vault_file = vault_path / "note.md"

        policy = Policy(
            plugin_name="test",
            granted_permissions=["fs.write"],
            sandbox_config=SandboxConfig(fs_write_paths=[str(tmp_path)]),
            vault_path=vault_path,
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_fs_write_access(vault_file)

        assert "Vault writes forbidden" in str(exc_info.value)
        assert "Host API" in str(exc_info.value)

    def test_check_fs_read_access_vault_forbidden(self, tmp_path):
        """Test direct vault reads are forbidden (ADR-006)."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        vault_file = vault_path / "note.md"

        policy = Policy(
            plugin_name="test",
            granted_permissions=["fs.read"],
            sandbox_config=SandboxConfig(fs_read_paths=[str(tmp_path)]),
            vault_path=vault_path,
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_fs_read_access(vault_file)

        assert "Vault access forbidden" in str(exc_info.value)
        assert "Host API" in str(exc_info.value)

    def test_get_violations_network_mismatch(self):
        """Test policy violations detection for network mismatch."""
        policy = Policy(
            plugin_name="test",
            granted_permissions=["net"],
            sandbox_config=SandboxConfig(network_access=False),
        )

        violations = policy.get_violations()

        assert len(violations) > 0
        assert any(v.permission == "net" for v in violations)

    def test_get_violations_fs_write_no_paths(self):
        """Test policy violations detection for fs.write without paths."""
        policy = Policy(
            plugin_name="test",
            granted_permissions=["fs.write"],
            sandbox_config=SandboxConfig(fs_write_paths=[]),
        )

        violations = policy.get_violations()

        assert len(violations) > 0
        assert any(v.permission == "fs.write" for v in violations)


class TestStandaloneHelpers:
    """Tests for standalone permission helper functions."""

    def test_check_permission_granted(self):
        """Test check_permission helper when granted."""
        # Should not raise
        check_permission("net", ["net", "vault.read"], "test-plugin")

    def test_check_permission_denied(self):
        """Test check_permission helper when denied."""
        with pytest.raises(PermissionDeniedError) as exc_info:
            check_permission("fs.write", ["net", "vault.read"], "test-plugin")

        assert "fs.write" in str(exc_info.value)
        assert "test-plugin" in str(exc_info.value)

    def test_check_fs_access_vault_forbidden(self, tmp_path):
        """Test check_fs_access helper for vault path."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        test_file = vault_path / "test.md"

        with pytest.raises(PermissionDeniedError) as exc_info:
            check_fs_access(test_file, "write", [str(tmp_path)], vault_path)

        assert "Vault" in str(exc_info.value)

    def test_check_fs_access_allowed(self, tmp_path):
        """Test check_fs_access helper when path allowed."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        test_file = allowed_dir / "test.txt"

        # Should not raise
        check_fs_access(test_file, "read", [str(allowed_dir)])

    def test_check_fs_access_denied_empty_allowlist(self, tmp_path):
        """Test check_fs_access helper with empty allowlist."""
        test_file = tmp_path / "test.txt"

        with pytest.raises(PermissionDeniedError) as exc_info:
            check_fs_access(test_file, "read", [])

        assert "No read paths configured" in str(exc_info.value)


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError exception."""

    def test_error_with_reason(self):
        """Test error message includes reason."""
        error = PermissionDeniedError("net", "Network access disabled")

        assert "net" in str(error)
        assert "Network access disabled" in str(error)

    def test_error_without_reason(self):
        """Test error message without reason."""
        error = PermissionDeniedError("vault.write")

        assert "vault.write" in str(error)


class TestPolicyViolation:
    """Tests for PolicyViolation dataclass."""

    def test_create_violation(self):
        """Test creating policy violation."""
        violation = PolicyViolation(
            permission="net",
            reason="Permission granted but network_access is False",
            context={"plugin": "test"},
        )

        assert violation.permission == "net"
        assert "network_access" in violation.reason
        assert violation.context["plugin"] == "test"
