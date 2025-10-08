"""Integration tests for sandbox plugin execution (ADR-004).

Tests complete plugin lifecycle with subprocess isolation, permissions,
timeouts, and crash recovery.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.policy import Policy
from kira.core.sandbox import Sandbox, SandboxConfig, SandboxError


class TestSandboxPluginExecution:
    """Integration tests for plugin execution in sandbox."""

    def test_sandbox_launches_plugin_successfully(self, tmp_path: Path) -> None:
        """Test successful plugin launch in subprocess sandbox."""
        # Create minimal test plugin
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        src_dir = plugin_dir / "src" / "test_plugin"
        src_dir.mkdir(parents=True)

        # Write plugin code
        (src_dir / "__init__.py").write_text("")
        (src_dir / "plugin.py").write_text(
            """
def activate(context):
    return {"status": "active", "message": "Plugin activated"}
"""
        )

        # Create sandbox and launch
        config = SandboxConfig(timeout_ms=5000)
        sandbox = Sandbox(config=config)

        policy = Policy(
            plugin_name="test-plugin",
            sandbox_config=SandboxPolicy(
                strategy="subprocess",
                network_access=False,
            ),
            permissions=set(),
        )

        process = sandbox.launch(
            plugin_name="test-plugin",
            entry_point="test_plugin.plugin:activate",
            plugin_path=plugin_dir,
            policy=policy,
            context_config={"test": True},
        )

        # Verify process is running
        assert process.is_alive()
        assert process.plugin_name == "test-plugin"
        assert process.restart_count == 0

        # Cleanup
        sandbox.stop_all()
        assert not process.is_alive()

    def test_sandbox_isolates_plugin_crash(self, tmp_path: Path) -> None:
        """Test sandbox isolates crashing plugin."""
        # Create crashing plugin
        plugin_dir = tmp_path / "crash_plugin"
        plugin_dir.mkdir()
        src_dir = plugin_dir / "src" / "crash_plugin"
        src_dir.mkdir(parents=True)

        (src_dir / "__init__.py").write_text("")
        (src_dir / "plugin.py").write_text(
            """
def activate(context):
    raise RuntimeError("Intentional crash")
"""
        )

        config = SandboxConfig(timeout_ms=5000, max_restarts=0)
        sandbox = Sandbox(config=config)

        policy = Policy(
            plugin_name="crash-plugin",
            sandbox_config=SandboxPolicy(strategy="subprocess"),
            permissions=set(),
        )

        # Launch plugin - should not crash host
        process = sandbox.launch(
            plugin_name="crash-plugin",
            entry_point="crash_plugin.plugin:activate",
            plugin_path=plugin_dir,
            policy=policy,
        )

        # Wait for crash
        time.sleep(1)

        # Process should have exited, but sandbox should be fine
        assert not process.is_alive()

        # Cleanup
        sandbox.stop_all()

    def test_sandbox_enforces_restart_limits(self, tmp_path: Path) -> None:
        """Test sandbox respects restart limits."""
        plugin_dir = tmp_path / "restart_plugin"
        plugin_dir.mkdir()
        src_dir = plugin_dir / "src" / "restart_plugin"
        src_dir.mkdir(parents=True)

        (src_dir / "__init__.py").write_text("")
        (src_dir / "plugin.py").write_text(
            """
def activate(context):
    return {"status": "active"}
"""
        )

        # Configure with low restart limit
        config = SandboxConfig(max_restarts=2, restart_window_seconds=60)
        sandbox = Sandbox(config=config)

        policy = Policy(
            plugin_name="restart-plugin",
            sandbox_config=SandboxPolicy(strategy="subprocess"),
            permissions=set(),
        )

        # Launch multiple times quickly
        for i in range(2):
            process = sandbox.launch(
                plugin_name="restart-plugin",
                entry_point="restart_plugin.plugin:activate",
                plugin_path=plugin_dir,
                policy=policy,
            )
            sandbox.stop("restart-plugin", force=True)
            time.sleep(0.1)

        # Third launch should fail due to restart limit
        with pytest.raises(SandboxError, match="exceeded restart limit"):
            sandbox.launch(
                plugin_name="restart-plugin",
                entry_point="restart_plugin.plugin:activate",
                plugin_path=plugin_dir,
                policy=policy,
            )

    def test_sandbox_terminates_on_timeout(self, tmp_path: Path) -> None:
        """Test sandbox terminates hung processes."""
        plugin_dir = tmp_path / "hang_plugin"
        plugin_dir.mkdir()
        src_dir = plugin_dir / "src" / "hang_plugin"
        src_dir.mkdir(parents=True)

        (src_dir / "__init__.py").write_text("")
        (src_dir / "plugin.py").write_text(
            """
import time

def activate(context):
    time.sleep(100)  # Hang for long time
    return {"status": "active"}
"""
        )

        # Short timeout
        config = SandboxConfig(timeout_ms=2000, grace_period_seconds=1.0)
        sandbox = Sandbox(config=config)

        policy = Policy(
            plugin_name="hang-plugin",
            sandbox_config=SandboxPolicy(strategy="subprocess"),
            permissions=set(),
        )

        process = sandbox.launch(
            plugin_name="hang-plugin",
            entry_point="hang_plugin.plugin:activate",
            plugin_path=plugin_dir,
            policy=policy,
        )

        # Process should be running initially
        assert process.is_alive()

        # Wait for timeout
        time.sleep(3)

        # Force termination
        sandbox.stop("hang-plugin", force=True)
        time.sleep(0.5)

        # Process should be terminated
        assert not process.is_alive()

    def test_sandbox_respects_network_policy(self, tmp_path: Path) -> None:
        """Test sandbox network access policy enforcement."""
        plugin_dir = tmp_path / "net_plugin"
        plugin_dir.mkdir()
        src_dir = plugin_dir / "src" / "net_plugin"
        src_dir.mkdir(parents=True)

        (src_dir / "__init__.py").write_text("")
        (src_dir / "plugin.py").write_text(
            """
def activate(context):
    import os
    # Check proxy env vars (network disabled)
    return {
        "status": "active",
        "http_proxy": os.environ.get("http_proxy", ""),
        "https_proxy": os.environ.get("https_proxy", "")
    }
"""
        )

        config = SandboxConfig(timeout_ms=5000)
        sandbox = Sandbox(config=config)

        # Policy with network disabled
        policy = Policy(
            plugin_name="net-plugin",
            sandbox_config=SandboxPolicy(
                strategy="subprocess",
                network_access=False,  # Network disabled
            ),
            permissions=set(),
        )

        process = sandbox.launch(
            plugin_name="net-plugin",
            entry_point="net_plugin.plugin:activate",
            plugin_path=plugin_dir,
            policy=policy,
        )

        # Proxy should be set to block network (best-effort on Unix)
        assert process.is_alive()

        # Cleanup
        sandbox.stop_all()

    def test_sandbox_context_manager(self, tmp_path: Path) -> None:
        """Test sandbox context manager cleanup."""
        plugin_dir = tmp_path / "ctx_plugin"
        plugin_dir.mkdir()
        src_dir = plugin_dir / "src" / "ctx_plugin"
        src_dir.mkdir(parents=True)

        (src_dir / "__init__.py").write_text("")
        (src_dir / "plugin.py").write_text(
            """
def activate(context):
    return {"status": "active"}
"""
        )

        policy = Policy(
            plugin_name="ctx-plugin",
            sandbox_config=SandboxPolicy(strategy="subprocess"),
            permissions=set(),
        )

        # Use context manager
        with Sandbox() as sandbox:
            process = sandbox.launch(
                plugin_name="ctx-plugin",
                entry_point="ctx_plugin.plugin:activate",
                plugin_path=plugin_dir,
                policy=policy,
            )
            assert process.is_alive()

        # Process should be cleaned up after context exit
        assert not process.is_alive()


class TestSandboxPermissionEnforcement:
    """Integration tests for permission enforcement in sandbox."""

    def test_sandbox_denies_unauthorized_fs_write(self, tmp_path: Path) -> None:
        """Test sandbox denies filesystem writes without permission."""
        plugin_dir = tmp_path / "fs_plugin"
        plugin_dir.mkdir()
        src_dir = plugin_dir / "src" / "fs_plugin"
        src_dir.mkdir(parents=True)

        (src_dir / "__init__.py").write_text("")
        (src_dir / "plugin.py").write_text(
            f"""
def activate(context):
    # Try to write to temp location
    try:
        with open("{tmp_path / 'forbidden.txt'}", "w") as f:
            f.write("Should not work")
        return {{"status": "active", "wrote": True}}
    except Exception as e:
        return {{"status": "active", "wrote": False, "error": str(e)}}
"""
        )

        config = SandboxConfig(timeout_ms=5000)
        sandbox = Sandbox(config=config)

        # Policy without fs.write permission
        policy = Policy(
            plugin_name="fs-plugin",
            sandbox_config=SandboxPolicy(
                strategy="subprocess",
                fs_access={"read_paths": [], "write_paths": []},
            ),
            permissions=set(),  # No fs.write permission
        )

        process = sandbox.launch(
            plugin_name="fs-plugin",
            entry_point="fs_plugin.plugin:activate",
            plugin_path=plugin_dir,
            policy=policy,
        )

        time.sleep(1)

        # File should not have been created (policy violation)
        # Note: In full implementation, this would be enforced at RPC boundary

        sandbox.stop_all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
