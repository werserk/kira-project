"""Tests for plugin sandbox (Phase 5, Point 16)."""

import tempfile
from pathlib import Path

from kira.plugins.sandbox import (
    PluginCapability,
    PluginSandbox,
    SandboxConfig,
    create_sandbox,
)


def test_sandbox_config_defaults():
    """Test sandbox configuration defaults."""
    config = SandboxConfig()

    assert config.max_cpu_seconds == 30.0
    assert config.max_memory_mb == 256
    assert config.max_wall_time_seconds == 60.0
    assert config.allow_network is False
    assert PluginCapability.VAULT_READ in config.allowed_capabilities
    assert PluginCapability.VAULT_SAVE in config.allowed_capabilities


def test_sandbox_initialization():
    """Test sandbox initialization."""
    sandbox = PluginSandbox()

    assert sandbox.config is not None
    assert sandbox.config.allow_network is False


def test_plugin_capabilities():
    """Test plugin capability constants."""
    assert PluginCapability.VAULT_READ == "vault.read"
    assert PluginCapability.VAULT_SAVE == "vault.save"
    assert PluginCapability.VAULT_LIST == "vault.list"
    assert PluginCapability.NETWORK == "network"


def test_sandbox_execute_nonexistent_plugin():
    """Test executing nonexistent plugin."""
    sandbox = PluginSandbox()

    result = sandbox.execute(Path("/nonexistent/plugin.py"))

    assert result.success is False
    assert "not found" in result.error.lower()


def test_sandbox_execute_simple_plugin():
    """Test executing simple plugin."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "test_plugin.py"
        plugin_path.write_text('print("Hello from plugin")')

        sandbox = PluginSandbox()
        result = sandbox.execute(plugin_path)

        assert result.success is True
        assert "Hello from plugin" in result.output
        assert result.duration_seconds > 0


def test_sandbox_execute_with_args():
    """Test executing plugin with arguments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "test_plugin.py"
        plugin_path.write_text(
            """
import sys
print(f"Args: {sys.argv[1:]}")
"""
        )

        sandbox = PluginSandbox()
        result = sandbox.execute(plugin_path, args=["arg1", "arg2"])

        assert result.success is True
        assert "arg1" in result.output
        assert "arg2" in result.output


def test_sandbox_capability_validation():
    """Test DoD: Plugins without capability cannot access resources."""
    config = SandboxConfig(allowed_capabilities=["vault.read"])
    sandbox = PluginSandbox(config)

    # Requesting allowed capability - should succeed
    assert sandbox.has_capability("vault.read") is True

    # Requesting disallowed capability - should fail
    assert sandbox.has_capability("network") is False


def test_sandbox_execute_with_capabilities():
    """Test executing plugin with capabilities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "test_plugin.py"
        plugin_path.write_text(
            """
import os
caps = os.environ.get("KIRA_CAPABILITIES", "")
print(f"Capabilities: {caps}")
"""
        )

        sandbox = PluginSandbox()
        result = sandbox.execute(
            plugin_path,
            capabilities=["vault.read", "vault.save"],
        )

        assert result.success is True
        assert "vault.read" in result.output
        assert "vault.save" in result.output


def test_sandbox_reject_disallowed_capability():
    """Test DoD: Reject plugins requesting disallowed capabilities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "test_plugin.py"
        plugin_path.write_text('print("Should not run")')

        config = SandboxConfig(allowed_capabilities=["vault.read"])
        sandbox = PluginSandbox(config)

        # Request disallowed capability
        result = sandbox.execute(
            plugin_path,
            capabilities=["network"],  # Not in allowed list
        )

        assert result.success is False
        assert "not allowed" in result.error.lower()


def test_sandbox_timeout():
    """Test sandbox enforces time limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "slow_plugin.py"
        plugin_path.write_text(
            """
import time
time.sleep(10)  # Sleep longer than timeout
print("Done")
"""
        )

        config = SandboxConfig(max_wall_time_seconds=0.5)  # 500ms timeout
        sandbox = PluginSandbox(config)

        result = sandbox.execute(plugin_path)

        assert result.success is False
        assert "time limit" in result.error.lower()


def test_sandbox_environment_variables():
    """Test sandbox passes environment variables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "test_plugin.py"
        plugin_path.write_text(
            """
import os
print(f"Custom: {os.environ.get('CUSTOM_VAR', 'not set')}")
print(f"Sandboxed: {os.environ.get('KIRA_SANDBOXED', 'no')}")
"""
        )

        sandbox = PluginSandbox()
        result = sandbox.execute(
            plugin_path,
            env={"CUSTOM_VAR": "test_value"},
        )

        assert result.success is True
        assert "test_value" in result.output
        assert "Sandboxed: 1" in result.output


def test_sandbox_error_handling():
    """Test sandbox handles plugin errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "error_plugin.py"
        plugin_path.write_text(
            """
raise RuntimeError("Plugin error")
"""
        )

        sandbox = PluginSandbox()
        result = sandbox.execute(plugin_path)

        assert result.success is False
        assert result.error is not None


def test_create_sandbox_factory():
    """Test factory function for creating sandbox."""
    sandbox = create_sandbox(
        max_cpu_seconds=10.0,
        max_memory_mb=128,
        allow_network=True,
    )

    assert sandbox.config.max_cpu_seconds == 10.0
    assert sandbox.config.max_memory_mb == 128
    assert sandbox.config.allow_network is True


def test_sandbox_default_no_network():
    """Test DoD: No network access by default."""
    sandbox = PluginSandbox()

    # Network not in default capabilities
    assert PluginCapability.NETWORK not in sandbox.config.allowed_capabilities

    # allow_network is False by default
    assert sandbox.config.allow_network is False


def test_sandbox_capability_based_api():
    """Test DoD: Capability-based API instead of raw FS access."""
    config = SandboxConfig(
        allowed_capabilities=["vault.read", "vault.save"]
        # No file.read or file.write - no raw FS access
    )
    sandbox = PluginSandbox(config)

    # Vault operations allowed
    assert sandbox.has_capability("vault.read") is True
    assert sandbox.has_capability("vault.save") is True

    # Raw file operations not allowed
    assert sandbox.has_capability("file.read") is False
    assert sandbox.has_capability("file.write") is False


def test_dod_plugins_without_capability_blocked():
    """Test DoD: Plugins without explicit capability cannot access arbitrary files or network."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "restricted_plugin.py"
        plugin_path.write_text('print("Restricted")')

        # Create sandbox with minimal capabilities
        config = SandboxConfig(
            allowed_capabilities=[],  # No capabilities
            allow_network=False,
        )
        sandbox = PluginSandbox(config)

        # Try to request network capability - should be rejected
        result = sandbox.execute(
            plugin_path,
            capabilities=["network"],
        )

        assert result.success is False
        assert "not allowed" in result.error.lower()

        # Try to request file access - should be rejected
        result = sandbox.execute(
            plugin_path,
            capabilities=["file.write"],
        )

        assert result.success is False


def test_sandbox_resource_limits_config():
    """Test resource limits are configurable."""
    config = SandboxConfig(
        max_cpu_seconds=5.0,
        max_memory_mb=64,
        max_wall_time_seconds=10.0,
    )

    assert config.max_cpu_seconds == 5.0
    assert config.max_memory_mb == 64
    assert config.max_wall_time_seconds == 10.0


def test_sandbox_measures_duration():
    """Test sandbox measures execution duration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "test_plugin.py"
        plugin_path.write_text(
            """
import time
time.sleep(0.1)
print("Done")
"""
        )

        sandbox = PluginSandbox()
        result = sandbox.execute(plugin_path)

        assert result.success is True
        assert result.duration_seconds >= 0.1


def test_sandbox_success_result():
    """Test successful plugin returns proper result."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "test_plugin.py"
        plugin_path.write_text('print("Success output")')

        sandbox = PluginSandbox()
        result = sandbox.execute(plugin_path)

        assert result.success is True
        assert result.output == "Success output\n"
        assert result.error is None
        assert result.duration_seconds > 0


def test_sandbox_failure_result():
    """Test failed plugin returns proper result."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "fail_plugin.py"
        plugin_path.write_text(
            """
import sys
sys.stderr.write("Error message")
sys.exit(1)
"""
        )

        sandbox = PluginSandbox()
        result = sandbox.execute(plugin_path)

        assert result.success is False
        assert "Error message" in result.error or "Exit code 1" in result.error
        assert result.duration_seconds > 0
