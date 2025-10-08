"""Subprocess-based sandbox for plugin execution.

Implements ADR-004: subprocess isolation with JSON-RPC 2.0 over stdio,
permission enforcement, resource limits, and lifecycle management.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .policy import Policy

from ..plugin_sdk.rpc import JSONRPCError, JSONRPCMessage, parse_jsonrpc_message, serialize_jsonrpc_message

__all__ = [
    "PluginProcess",
    "Sandbox",
    "SandboxConfig",
    "SandboxError",
    "create_sandbox",
]


class SandboxError(Exception):
    """Raised when sandbox operations fail."""

    pass


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""

    strategy: str = "subprocess"
    timeout_ms: int = 30000
    memory_limit_mb: int | None = None
    max_restarts: int = 3
    restart_window_seconds: int = 300
    grace_period_seconds: float = 5.0
    env_whitelist: list[str] = field(default_factory=lambda: ["PATH", "HOME", "USER"])


@dataclass
class PluginProcess:
    """Container for subprocess plugin execution state."""

    process: subprocess.Popen[bytes]
    plugin_name: str
    entry_point: str
    policy: Policy
    config: SandboxConfig
    started_at: float = field(default_factory=time.time)
    restart_count: int = 0
    is_stopping: bool = False

    def is_alive(self) -> bool:
        """Check if process is still running."""
        return self.process.poll() is None

    def send_message(self, message: JSONRPCMessage) -> None:
        """Send JSON-RPC message to plugin process.

        Parameters
        ----------
        message
            Message to send

        Raises
        ------
        SandboxError
            If process is not running or write fails
        """
        if not self.is_alive():
            raise SandboxError(f"Plugin process {self.plugin_name} is not running")

        if self.process.stdin is None:
            raise SandboxError(f"Plugin process {self.plugin_name} has no stdin")

        try:
            data = serialize_jsonrpc_message(message)
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise SandboxError(f"Failed to send message to {self.plugin_name}: {exc}") from exc

    def receive_message(self, timeout: float | None = None) -> JSONRPCMessage:
        """Receive JSON-RPC message from plugin process.

        Parameters
        ----------
        timeout
            Timeout in seconds (None for no timeout)

        Returns
        -------
        JSONRPCMessage
            Received message

        Raises
        ------
        SandboxError
            If process is not running or read fails
        TimeoutError
            If timeout expires
        """
        if not self.is_alive():
            raise SandboxError(f"Plugin process {self.plugin_name} is not running")

        if self.process.stdout is None:
            raise SandboxError(f"Plugin process {self.plugin_name} has no stdout")

        # Read with timeout
        result: list[JSONRPCMessage | Exception] = []

        def read_worker() -> None:
            try:
                # Read Content-Length header
                header = self.process.stdout.readline()  # type: ignore
                if not header:
                    result.append(SandboxError("Process stdout closed"))
                    return

                # Parse Content-Length
                if not header.startswith(b"Content-Length:"):
                    result.append(
                        JSONRPCError(
                            f"Expected Content-Length, got: {header!r}",
                            JSONRPCError.PARSE_ERROR,
                        )
                    )
                    return

                content_length = int(header.decode("ascii").split(":")[1].strip())

                # Read empty line
                empty = self.process.stdout.readline()  # type: ignore
                if empty != b"\r\n":
                    result.append(
                        JSONRPCError(
                            f"Expected empty line, got: {empty!r}",
                            JSONRPCError.PARSE_ERROR,
                        )
                    )
                    return

                # Read content
                content = self.process.stdout.read(content_length)  # type: ignore
                if len(content) != content_length:
                    result.append(
                        JSONRPCError(
                            f"Expected {content_length} bytes, got {len(content)}",
                            JSONRPCError.PARSE_ERROR,
                        )
                    )
                    return

                message = parse_jsonrpc_message(content)
                result.append(message)
            except Exception as exc:
                result.append(exc)

        thread = threading.Thread(target=read_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise TimeoutError(f"Timeout reading from {self.plugin_name} (timeout={timeout}s)")

        if not result:
            raise SandboxError(f"No response from {self.plugin_name}")

        if isinstance(result[0], Exception):
            raise result[0]

        return result[0]

    def terminate(self, force: bool = False) -> None:
        """Terminate plugin process.

        Parameters
        ----------
        force
            If True, use SIGKILL immediately. If False, try SIGTERM first.
        """
        if not self.is_alive():
            return

        self.is_stopping = True

        if force:
            self.process.kill()
        else:
            self.process.terminate()
            try:
                self.process.wait(timeout=self.config.grace_period_seconds)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                self.process.kill()
                self.process.wait(timeout=1.0)


class Sandbox:
    """Subprocess-based sandbox for plugin execution.

    Implements ADR-004: spawns plugins in isolated subprocesses with JSON-RPC
    communication, permission enforcement, timeouts, and resource limits.
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """Initialize sandbox manager.

        Parameters
        ----------
        config
            Sandbox configuration (default: SandboxConfig())
        """
        self.config = config or SandboxConfig()
        self._processes: dict[str, PluginProcess] = {}
        self._restart_times: dict[str, list[float]] = {}

    def launch(
        self,
        plugin_name: str,
        entry_point: str,
        plugin_path: Path,
        policy: Policy,
        context_config: dict[str, Any] | None = None,
    ) -> PluginProcess:
        """Launch plugin in subprocess sandbox.

        Parameters
        ----------
        plugin_name
            Plugin identifier
        entry_point
            Entry point in format "module:function"
        plugin_path
            Path to plugin directory
        policy
            Permission policy for the plugin
        context_config
            Configuration to pass to plugin context

        Returns
        -------
        PluginProcess
            Running plugin process

        Raises
        ------
        SandboxError
            If launch fails
        """
        # Check restart limits
        if not self._check_restart_allowed(plugin_name):
            raise SandboxError(
                f"Plugin {plugin_name} exceeded restart limit "
                f"({self.config.max_restarts} restarts in "
                f"{self.config.restart_window_seconds}s)"
            )

        # Prepare environment
        env = self._prepare_environment(policy)

        # Prepare Python command
        module_name, func_name = entry_point.split(":", 1)
        src_path = plugin_path / "src"

        # Create launcher script
        launcher_code = f"""
import sys
import json
sys.path.insert(0, {str(src_path)!r})

# Import plugin module
try:
    import {module_name}
    activate_func = getattr({module_name}, {func_name!r})
except (ImportError, AttributeError) as exc:
    print(f"ERROR: Failed to import {entry_point}: {{exc}}", file=sys.stderr)
    sys.exit(1)

# Import SDK components
from kira.plugin_sdk.context import PluginContext
from kira.plugin_sdk.rpc import StdioTransport, HostRPCClient

# Create context
config = {context_config!r}
transport = StdioTransport()
context = PluginContext(
    config=config,
    # RPC client would be injected here for real host API calls
)

# Activate plugin
try:
    result = activate_func(context)
    print(f"Plugin activated: {{result}}", file=sys.stderr)
except Exception as exc:
    print(f"ERROR: Plugin activation failed: {{exc}}", file=sys.stderr)
    sys.exit(1)

# Keep alive for RPC communication
# In real implementation, this would enter RPC serve loop
import time
print("Plugin running...", file=sys.stderr)
time.sleep({self.config.timeout_ms / 1000.0})
"""

        # Launch subprocess
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", launcher_code],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=str(plugin_path),
                # Resource limits (platform-specific)
                preexec_fn=self._setup_resource_limits if sys.platform != "win32" else None,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise SandboxError(f"Failed to launch {plugin_name}: {exc}") from exc

        # Create process container
        plugin_process = PluginProcess(
            process=process,
            plugin_name=plugin_name,
            entry_point=entry_point,
            policy=policy,
            config=self.config,
            started_at=time.time(),
            restart_count=self._get_restart_count(plugin_name),
        )

        self._processes[plugin_name] = plugin_process
        self._record_restart(plugin_name)

        return plugin_process

    def _prepare_environment(self, policy: Policy) -> dict[str, str]:
        """Prepare sanitized environment for subprocess.

        Parameters
        ----------
        policy
            Plugin policy

        Returns
        -------
        dict
            Environment variables
        """
        # Start with minimal environment
        env = {}

        # Add whitelisted vars
        for var in self.config.env_whitelist:
            if var in os.environ:
                env[var] = os.environ[var]

        # Add Python path
        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = ":".join(sys.path)

        # Disable network if not permitted
        if not policy.sandbox_config.network_access:
            # This is best-effort on Unix-like systems
            env["http_proxy"] = "http://0.0.0.0:0"
            env["https_proxy"] = "http://0.0.0.0:0"
            env["no_proxy"] = "*"

        return env

    def _setup_resource_limits(self) -> None:
        """Setup resource limits for subprocess (Unix-only).

        Called via preexec_fn, runs in child process before exec.
        """
        try:
            import resource

            # Set memory limit if configured
            if self.config.memory_limit_mb:
                mem_bytes = self.config.memory_limit_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

            # Prevent core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

            # Limit CPU time (soft limit = timeout + 10s)
            cpu_limit = (self.config.timeout_ms // 1000) + 10
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 5))

        except (ImportError, OSError):
            # Resource limits not available on this platform
            pass

    def _check_restart_allowed(self, plugin_name: str) -> bool:
        """Check if plugin is allowed to restart.

        Parameters
        ----------
        plugin_name
            Plugin identifier

        Returns
        -------
        bool
            True if restart is allowed
        """
        if plugin_name not in self._restart_times:
            return True

        # Clean old restart times
        cutoff = time.time() - self.config.restart_window_seconds
        self._restart_times[plugin_name] = [t for t in self._restart_times[plugin_name] if t > cutoff]

        return len(self._restart_times[plugin_name]) < self.config.max_restarts

    def _record_restart(self, plugin_name: str) -> None:
        """Record restart time for rate limiting."""
        if plugin_name not in self._restart_times:
            self._restart_times[plugin_name] = []
        self._restart_times[plugin_name].append(time.time())

    def _get_restart_count(self, plugin_name: str) -> int:
        """Get current restart count within window."""
        if plugin_name not in self._restart_times:
            return 0
        return len(self._restart_times[plugin_name])

    def get_process(self, plugin_name: str) -> PluginProcess | None:
        """Get running process for plugin.

        Parameters
        ----------
        plugin_name
            Plugin identifier

        Returns
        -------
        PluginProcess or None
            Process if running, None otherwise
        """
        return self._processes.get(plugin_name)

    def stop(self, plugin_name: str, force: bool = False) -> None:
        """Stop plugin process.

        Parameters
        ----------
        plugin_name
            Plugin identifier
        force
            If True, use SIGKILL immediately
        """
        process = self._processes.get(plugin_name)
        if process:
            process.terminate(force=force)
            del self._processes[plugin_name]

    def stop_all(self, force: bool = False) -> None:
        """Stop all running plugin processes.

        Parameters
        ----------
        force
            If True, use SIGKILL immediately
        """
        for plugin_name in list(self._processes.keys()):
            self.stop(plugin_name, force=force)

    def __enter__(self) -> Sandbox:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - stop all processes."""
        self.stop_all(force=True)


def create_sandbox(
    strategy: str = "subprocess",
    timeout_ms: int = 30000,
    **kwargs: Any,
) -> Sandbox:
    """Create sandbox instance.

    Parameters
    ----------
    strategy
        Sandbox strategy ("subprocess", "thread", "inline")
    timeout_ms
        Default timeout in milliseconds
    **kwargs
        Additional SandboxConfig parameters

    Returns
    -------
    Sandbox
        Configured sandbox instance

    Raises
    ------
    ValueError
        If strategy is not "subprocess" (others not yet implemented)
    """
    if strategy != "subprocess":
        raise ValueError(f"Only 'subprocess' strategy is implemented, got: {strategy}")

    config = SandboxConfig(strategy=strategy, timeout_ms=timeout_ms, **kwargs)
    return Sandbox(config=config)
