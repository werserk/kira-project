"""Tests for subprocess sandbox implementation (ADR-004)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.policy import Policy
from kira.core.policy import SandboxConfig as PolicySandboxConfig
from kira.core.sandbox import PluginProcess, Sandbox, SandboxConfig, SandboxError, create_sandbox


class TestSandboxConfig:
    """Tests for SandboxConfig."""

    def test_default_config(self):
        """Test default sandbox configuration."""
        config = SandboxConfig()

        assert config.strategy == "subprocess"
        assert config.timeout_ms == 30000
        assert config.memory_limit_mb is None
        assert config.max_restarts == 3
        assert config.restart_window_seconds == 300
        assert config.grace_period_seconds == 5.0

    def test_custom_config(self):
        """Test custom sandbox configuration."""
        config = SandboxConfig(
            strategy="subprocess",
            timeout_ms=60000,
            memory_limit_mb=256,
            max_restarts=5,
        )

        assert config.timeout_ms == 60000
        assert config.memory_limit_mb == 256
        assert config.max_restarts == 5


class TestSandbox:
    """Tests for Sandbox class."""

    def test_create_sandbox(self):
        """Test creating sandbox instance."""
        sandbox = Sandbox()

        assert sandbox.config.strategy == "subprocess"
        assert sandbox.config.timeout_ms == 30000

    def test_create_sandbox_with_config(self):
        """Test creating sandbox with custom config."""
        config = SandboxConfig(timeout_ms=45000)
        sandbox = Sandbox(config=config)

        assert sandbox.config.timeout_ms == 45000

    def test_get_process_not_found(self):
        """Test getting non-existent process."""
        sandbox = Sandbox()
        process = sandbox.get_process("non-existent")

        assert process is None

    def test_check_restart_allowed_initial(self):
        """Test restart allowed initially."""
        sandbox = Sandbox()

        assert sandbox._check_restart_allowed("test-plugin") is True

    def test_check_restart_allowed_within_limit(self):
        """Test restart allowed within limit."""
        sandbox = Sandbox()

        # Record some restarts
        for _ in range(2):
            sandbox._record_restart("test-plugin")

        assert sandbox._check_restart_allowed("test-plugin") is True

    def test_check_restart_allowed_exceeded(self):
        """Test restart blocked when limit exceeded."""
        sandbox = Sandbox(SandboxConfig(max_restarts=3))

        # Record max restarts
        for _ in range(3):
            sandbox._record_restart("test-plugin")

        assert sandbox._check_restart_allowed("test-plugin") is False

    def test_prepare_environment_minimal(self):
        """Test preparing minimal environment."""
        sandbox = Sandbox()
        manifest = {"permissions": []}
        policy = Policy.from_manifest(manifest)

        env = sandbox._prepare_environment(policy)

        assert "PYTHONPATH" in env
        # Whitelist vars should be present if in os.environ
        assert isinstance(env, dict)

    def test_prepare_environment_network_disabled(self):
        """Test environment with network disabled."""
        sandbox = Sandbox()
        manifest = {"permissions": []}
        policy = Policy.from_manifest(manifest)

        env = sandbox._prepare_environment(policy)

        # Network should be disabled via proxy vars
        assert "http_proxy" in env
        assert "https_proxy" in env

    def test_context_manager(self):
        """Test sandbox as context manager."""
        with Sandbox() as sandbox:
            assert isinstance(sandbox, Sandbox)

        # After exit, processes should be stopped (none were started)
        assert len(sandbox._processes) == 0


class TestCreateSandbox:
    """Tests for create_sandbox factory function."""

    def test_create_subprocess_sandbox(self):
        """Test creating subprocess sandbox."""
        sandbox = create_sandbox(strategy="subprocess", timeout_ms=45000)

        assert isinstance(sandbox, Sandbox)
        assert sandbox.config.strategy == "subprocess"
        assert sandbox.config.timeout_ms == 45000

    def test_create_sandbox_unsupported_strategy(self):
        """Test creating sandbox with unsupported strategy."""
        with pytest.raises(ValueError) as exc_info:
            create_sandbox(strategy="thread")

        assert "subprocess" in str(exc_info.value)
        assert "thread" in str(exc_info.value)


class TestPluginProcess:
    """Tests for PluginProcess container."""

    def test_plugin_process_attributes(self):
        """Test PluginProcess has expected attributes."""
        # Note: We can't easily create a real subprocess.Popen in tests
        # without complex setup, so we'll test what we can
        from unittest.mock import MagicMock

        mock_process = MagicMock()
        mock_process.poll.return_value = None

        policy = Policy(
            plugin_name="test",
            granted_permissions=[],
            sandbox_config=PolicySandboxConfig(),
        )

        plugin_process = PluginProcess(
            process=mock_process,
            plugin_name="test-plugin",
            entry_point="module:function",
            policy=policy,
            config=SandboxConfig(),
        )

        assert plugin_process.plugin_name == "test-plugin"
        assert plugin_process.entry_point == "module:function"
        assert plugin_process.restart_count == 0
        assert plugin_process.is_stopping is False

    def test_plugin_process_is_alive(self):
        """Test checking if plugin process is alive."""
        from unittest.mock import MagicMock

        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process running

        policy = Policy(
            plugin_name="test",
            granted_permissions=[],
            sandbox_config=PolicySandboxConfig(),
        )

        plugin_process = PluginProcess(
            process=mock_process,
            plugin_name="test",
            entry_point="m:f",
            policy=policy,
            config=SandboxConfig(),
        )

        assert plugin_process.is_alive() is True

        # Process exited
        mock_process.poll.return_value = 0
        assert plugin_process.is_alive() is False


class TestSandboxIntegration:
    """Integration tests for sandbox (mocked subprocess)."""

    def test_launch_requires_valid_policy(self, tmp_path):
        """Test launching requires valid policy and working entry point."""
        sandbox = Sandbox()

        plugin_path = tmp_path / "test-plugin"
        plugin_path.mkdir()
        src_path = plugin_path / "src"
        src_path.mkdir()

        # Create a minimal plugin module
        module_path = src_path / "test_module.py"
        module_path.write_text("""
def activate(context):
    return {"status": "ok", "message": "Test plugin activated"}
""")

        manifest = {
            "name": "test-plugin",
            "permissions": [],
            "entry": "test_module:activate",
        }
        policy = Policy.from_manifest(manifest)

        # Launch should succeed with valid policy and entry point
        process = sandbox.launch(
            plugin_name="test",
            entry_point="test_module:activate",
            plugin_path=plugin_path,
            policy=policy,
        )

        # Process should be running
        assert process.is_alive()

        # Clean up
        sandbox.stop("test")


class TestSandboxADR004Compliance:
    """Tests verifying ADR-004 requirements."""

    def test_subprocess_strategy_required(self):
        """Test that subprocess is the default and required strategy."""
        sandbox = create_sandbox()
        assert sandbox.config.strategy == "subprocess"

        with pytest.raises(ValueError):
            create_sandbox(strategy="inline")

    def test_timeout_configurable(self):
        """Test that timeout is configurable."""
        sandbox = create_sandbox(timeout_ms=45000)
        assert sandbox.config.timeout_ms == 45000

    def test_restart_limits_configurable(self):
        """Test that restart limits are configurable."""
        config = SandboxConfig(max_restarts=5, restart_window_seconds=600)
        sandbox = Sandbox(config=config)

        assert sandbox.config.max_restarts == 5
        assert sandbox.config.restart_window_seconds == 600

    def test_grace_period_for_shutdown(self):
        """Test that grace period is configured for graceful shutdown."""
        config = SandboxConfig(grace_period_seconds=10.0)
        sandbox = Sandbox(config=config)

        assert sandbox.config.grace_period_seconds == 10.0
