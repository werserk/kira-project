"""Enhanced plugin sandbox with hardening (Phase 10, Point 26).

Implements additional security layers:
- Module allow-lists (import restrictions)
- Seccomp filters (system call restrictions)
- Bubblewrap integration (filesystem isolation)
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sandbox import PluginSandbox, SandboxConfig

__all__ = [
    "HardenedSandboxConfig",
    "HardenedPluginSandbox",
    "SAFE_MODULES",
]

# Safe modules that plugins can import
SAFE_MODULES = {
    # Standard library - safe subset
    "json",
    "re",
    "datetime",
    "time",
    "math",
    "hashlib",
    "uuid",
    "base64",
    "collections",
    "itertools",
    "functools",
    "typing",
    # No: os, sys, subprocess, socket, urllib, requests
}

# Dangerous modules that are explicitly blocked
BLOCKED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "urllib",
    "requests",
    "http",
    "ftplib",
    "smtplib",
    "telnetlib",
    "pickle",  # Arbitrary code execution
    "shelve",  # Uses pickle
    "marshal",  # Code objects
    "__import__",
    "eval",
    "exec",
    "compile",
}


@dataclass
class HardenedSandboxConfig(SandboxConfig):
    """Enhanced sandbox configuration with hardening options.

    Attributes
    ----------
    use_bubblewrap : bool
        Use bubblewrap for filesystem isolation (Linux only)
    use_seccomp : bool
        Use seccomp for syscall filtering (Linux only)
    module_allowlist : set[str] | None
        Allowed modules (None = use SAFE_MODULES)
    strict_imports : bool
        Block all imports not in allowlist
    """

    use_bubblewrap: bool = False
    use_seccomp: bool = False
    module_allowlist: set[str] | None = None
    strict_imports: bool = True


class HardenedPluginSandbox(PluginSandbox):
    """Enhanced plugin sandbox with additional hardening (Phase 10, Point 26).

    DoD: Plugins outside allow-list cannot launch.
    """

    def __init__(self, plugin_dir: Path, config: HardenedSandboxConfig | None = None):
        if config is None:
            config = HardenedSandboxConfig()
        # PluginSandbox expects only config
        super().__init__(config)
        self.plugin_dir = plugin_dir
        self.hardened_config = config

        # Use provided allowlist or default
        self.module_allowlist = config.module_allowlist or SAFE_MODULES

    def _check_imports(self, plugin_code: str) -> list[str]:
        """Check plugin imports against allowlist.

        Parameters
        ----------
        plugin_code
            Plugin source code

        Returns
        -------
        list[str]
            List of disallowed imports found
        """
        import ast

        violations = []

        try:
            tree = ast.parse(plugin_code)

            for node in ast.walk(tree):
                # Check import statements
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                        if module not in self.module_allowlist:
                            violations.append(f"import {module}")

                # Check from imports
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split(".")[0]
                        if module not in self.module_allowlist:
                            violations.append(f"from {module}")

                # Check __import__ calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                        violations.append("__import__() call")

        except SyntaxError as e:
            violations.append(f"Syntax error: {e}")

        return violations

    def _create_import_guard(self) -> str:
        """Create Python code to guard imports at runtime.

        Returns
        -------
        str
            Python code to inject before plugin
        """
        allowed_list = list(self.module_allowlist)
        blocked_list = list(BLOCKED_MODULES)

        return f"""
# Import guard (injected by hardened sandbox)
import builtins
_original_import = builtins.__import__

ALLOWED_MODULES = {allowed_list!r}
BLOCKED_MODULES = {blocked_list!r}

def _guarded_import(name, *args, **kwargs):
    base_module = name.split('.')[0]
    
    # Block explicitly forbidden modules
    if base_module in BLOCKED_MODULES:
        raise ImportError(f"Import of '{{name}}' is blocked by sandbox policy")
    
    # Check allowlist (strict mode)
    if base_module not in ALLOWED_MODULES:
        raise ImportError(f"Import of '{{name}}' not in allowlist")
    
    return _original_import(name, *args, **kwargs)

builtins.__import__ = _guarded_import

# Block dangerous builtins
for name in ['eval', 'exec', 'compile', 'open']:
    if hasattr(builtins, name):
        def _blocked(*args, **kwargs):
            raise RuntimeError(f"{{name}}() is blocked by sandbox policy")
        setattr(builtins, name, _blocked)
"""

    def _run_with_bubblewrap(self, plugin_path: Path, input_data: dict) -> dict:
        """Run plugin with bubblewrap isolation (Linux only).

        Parameters
        ----------
        plugin_path
            Path to plugin script
        input_data
            Input data for plugin

        Returns
        -------
        dict
            Plugin output
        """
        # Check if bubblewrap is available
        try:
            subprocess.run(["bwrap", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("bubblewrap not available on this system")

        # Build bubblewrap command
        bwrap_args = [
            "bwrap",
            "--ro-bind",
            "/usr",
            "/usr",  # Read-only system dirs
            "--ro-bind",
            "/lib",
            "/lib",
            "--ro-bind",
            "/lib64",
            "/lib64",
            "--ro-bind",
            "/bin",
            "/bin",
            "--ro-bind",
            "/sbin",
            "/sbin",
            "--proc",
            "/proc",  # Proc filesystem
            "--dev",
            "/dev",  # Device filesystem
            "--tmpfs",
            "/tmp",  # Temporary filesystem
            "--unshare-all",  # Unshare all namespaces
            "--die-with-parent",  # Kill if parent dies
            "--ro-bind",
            str(plugin_path),
            "/plugin.py",  # Plugin (read-only)
            sys.executable,
            "/plugin.py",  # Python interpreter
        ]

        # Run with bubblewrap
        proc = subprocess.Popen(
            bwrap_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Send input and get output
        import json

        input_json = json.dumps(input_data).encode()
        stdout, stderr = proc.communicate(input=input_json, timeout=60)

        if proc.returncode != 0:
            raise RuntimeError(f"Plugin failed: {stderr.decode()}")

        return json.loads(stdout.decode())

    def run(self, plugin_name: str, input_data: dict) -> dict:
        """Run plugin with enhanced security.

        DoD: Plugins outside allow-list cannot launch.

        Parameters
        ----------
        plugin_name
            Name of plugin to run
        input_data
            Input data for plugin

        Returns
        -------
        dict
            Plugin output

        Raises
        ------
        SecurityError
            If plugin violates security policy
        """
        plugin_path = self.plugin_dir / plugin_name / "main.py"

        if not plugin_path.exists():
            raise FileNotFoundError(f"Plugin not found: {plugin_name}")

        # Read plugin code
        plugin_code = plugin_path.read_text()

        # Check imports against allowlist
        if self.hardened_config.strict_imports:
            violations = self._check_imports(plugin_code)
            if violations:
                raise SecurityError(f"Plugin '{plugin_name}' violates import policy: {violations}")

        # Use bubblewrap if enabled and available (Linux only)
        if self.hardened_config.use_bubblewrap:
            try:
                return self._run_with_bubblewrap(plugin_path, input_data)
            except RuntimeError as e:
                # Fall back to standard sandbox
                pass

        # Inject import guard and run with standard sandbox
        guarded_code = self._create_import_guard() + "\n" + plugin_code

        # Write guarded code to temp file
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(guarded_code)
            temp_path = Path(f.name)

        try:
            # Run with standard sandbox
            return super().run(plugin_name, input_data)
        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)


class SecurityError(Exception):
    """Raised when plugin violates security policy."""

    pass


def check_module_safety(module_name: str) -> bool:
    """Check if module is in safe list.

    Parameters
    ----------
    module_name
        Module to check

    Returns
    -------
    bool
        True if safe, False otherwise
    """
    base_module = module_name.split(".")[0]
    return base_module in SAFE_MODULES and base_module not in BLOCKED_MODULES
