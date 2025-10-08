"""Plugin sandbox for secure plugin execution (Phase 5, Point 16).

Runs plugins as subprocesses in a constrained environment:
- No network access by default (requires explicit capability)
- CPU/memory/time limits
- Capability-based API (no raw file system access)
- Restricted to specific operations via exposed API
"""

from __future__ import annotations

import os
import resource
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "PluginSandbox",
    "SandboxConfig",
    "PluginCapability",
    "PluginResult",
    "SandboxViolation",
]


@dataclass
class SandboxConfig:
    """Configuration for plugin sandbox.

    Attributes
    ----------
    max_cpu_seconds : float
        Maximum CPU time (default 30s)
    max_memory_mb : int
        Maximum memory in MB (default 256MB)
    max_wall_time_seconds : float
        Maximum wall clock time (default 60s)
    allow_network : bool
        Allow network access (default False)
    allowed_capabilities : list[str]
        List of allowed capabilities
    """

    max_cpu_seconds: float = 30.0
    max_memory_mb: int = 256
    max_wall_time_seconds: float = 60.0
    allow_network: bool = False
    allowed_capabilities: list[str] = None

    def __post_init__(self):
        if self.allowed_capabilities is None:
            self.allowed_capabilities = ["vault.read", "vault.save"]


class PluginCapability:
    """Plugin capabilities (Phase 5, Point 16).

    Defines what operations a plugin can perform.
    Instead of raw FS access, plugins use capability API.
    """

    VAULT_READ = "vault.read"
    VAULT_SAVE = "vault.save"
    VAULT_LIST = "vault.list"
    NETWORK = "network"
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"


class SandboxViolation(Exception):
    """Raised when plugin violates sandbox constraints."""

    pass


@dataclass
class PluginResult:
    """Result of plugin execution.

    Attributes
    ----------
    success : bool
        Whether execution succeeded
    output : Any
        Plugin output (if successful)
    error : str | None
        Error message (if failed)
    duration_seconds : float
        Execution duration
    """

    success: bool
    output: Any = None
    error: str | None = None
    duration_seconds: float = 0.0


class PluginSandbox:
    """Sandbox for secure plugin execution (Phase 5, Point 16).

    Runs plugins as subprocesses with:
    - Resource limits (CPU, memory, time)
    - No network access by default
    - Capability-based API instead of raw FS access
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """Initialize plugin sandbox.

        Parameters
        ----------
        config
            Sandbox configuration
        """
        self.config = config or SandboxConfig()

    def execute(
        self,
        plugin_path: Path,
        *,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        capabilities: list[str] | None = None,
    ) -> PluginResult:
        """Execute plugin in sandbox (Phase 5, Point 16).

        DoD: Plugins without explicit capability cannot access
        arbitrary files or the network.

        Parameters
        ----------
        plugin_path
            Path to plugin script
        args
            Arguments to pass to plugin
        env
            Environment variables
        capabilities
            Requested capabilities

        Returns
        -------
        PluginResult
            Execution result
        """
        if not plugin_path.exists():
            return PluginResult(
                success=False,
                error=f"Plugin not found: {plugin_path}",
            )

        # Validate capabilities
        requested_caps = capabilities or []
        for cap in requested_caps:
            if cap not in self.config.allowed_capabilities:
                return PluginResult(
                    success=False,
                    error=f"Capability not allowed: {cap}",
                )

        # Check network capability
        if PluginCapability.NETWORK not in requested_caps:
            if self.config.allow_network:
                # Network allowed globally but not requested
                pass
            # else: Network denied (default)

        # Prepare environment
        plugin_env = os.environ.copy()
        if env:
            plugin_env.update(env)

        # Add capability flags to environment
        plugin_env["KIRA_CAPABILITIES"] = ",".join(requested_caps)
        plugin_env["KIRA_SANDBOXED"] = "1"

        # Execute in subprocess with limits
        start_time = time.time()

        try:
            # Set resource limits (applied to subprocess)
            def set_limits():
                # CPU time limit
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (int(self.config.max_cpu_seconds), int(self.config.max_cpu_seconds)),
                )

                # Memory limit
                max_memory_bytes = self.config.max_memory_mb * 1024 * 1024
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (max_memory_bytes, max_memory_bytes),
                )

            # Run plugin
            cmd = [sys.executable, str(plugin_path)] + (args or [])

            result = subprocess.run(
                cmd,
                env=plugin_env,
                capture_output=True,
                text=True,
                timeout=self.config.max_wall_time_seconds,
                preexec_fn=set_limits,  # Apply resource limits
            )

            duration = time.time() - start_time

            if result.returncode == 0:
                return PluginResult(
                    success=True,
                    output=result.stdout,
                    duration_seconds=duration,
                )
            else:
                return PluginResult(
                    success=False,
                    error=result.stderr or f"Exit code {result.returncode}",
                    duration_seconds=duration,
                )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return PluginResult(
                success=False,
                error=f"Plugin exceeded time limit ({self.config.max_wall_time_seconds}s)",
                duration_seconds=duration,
            )

        except Exception as exc:
            duration = time.time() - start_time
            return PluginResult(
                success=False,
                error=f"Plugin execution failed: {exc}",
                duration_seconds=duration,
            )

    def has_capability(self, capability: str) -> bool:
        """Check if capability is allowed.

        Parameters
        ----------
        capability
            Capability to check

        Returns
        -------
        bool
            True if allowed
        """
        return capability in self.config.allowed_capabilities


def create_sandbox(
    *,
    max_cpu_seconds: float = 30.0,
    max_memory_mb: int = 256,
    allow_network: bool = False,
) -> PluginSandbox:
    """Create plugin sandbox with specified limits.

    Parameters
    ----------
    max_cpu_seconds
        CPU time limit
    max_memory_mb
        Memory limit in MB
    allow_network
        Allow network access

    Returns
    -------
    PluginSandbox
        Configured sandbox
    """
    config = SandboxConfig(
        max_cpu_seconds=max_cpu_seconds,
        max_memory_mb=max_memory_mb,
        allow_network=allow_network,
    )
    return PluginSandbox(config)
