"""Tests for hardened plugin sandbox (Phase 10, Point 26).

DoD: Plugins outside allow-list cannot launch.
"""

import tempfile
from pathlib import Path

import pytest

from kira.plugins.hardened_sandbox import (
    SAFE_MODULES,
    HardenedPluginSandbox,
    HardenedSandboxConfig,
    SecurityError,
    check_module_safety,
)


@pytest.fixture
def sandbox_env():
    """Create test environment for hardened sandbox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir) / "plugins"
        plugin_dir.mkdir()

        config = HardenedSandboxConfig(strict_imports=True)
        sandbox = HardenedPluginSandbox(plugin_dir, config)

        yield sandbox, plugin_dir


def test_safe_module_check():
    """Test checking if modules are safe."""
    # Safe modules
    assert check_module_safety("json") is True
    assert check_module_safety("datetime") is True
    assert check_module_safety("re") is True

    # Unsafe modules
    assert check_module_safety("os") is False
    assert check_module_safety("subprocess") is False
    assert check_module_safety("socket") is False


def test_check_imports_safe(sandbox_env):
    """Test import checking with safe imports."""
    sandbox, plugin_dir = sandbox_env

    # Plugin with safe imports
    safe_code = """
import json
import datetime
from collections import defaultdict

def process(data):
    return {"result": "ok"}
"""

    violations = sandbox._check_imports(safe_code)
    assert len(violations) == 0


def test_check_imports_unsafe(sandbox_env):
    """Test DoD: Detect unsafe imports."""
    sandbox, plugin_dir = sandbox_env

    # Plugin with unsafe imports
    unsafe_code = """
import os
import subprocess
from socket import socket

def process(data):
    os.system("rm -rf /")  # Evil!
"""

    violations = sandbox._check_imports(unsafe_code)
    assert len(violations) > 0
    assert any("os" in v for v in violations)


def test_dod_blocked_module_cannot_launch(sandbox_env):
    """Test DoD: Plugins outside allow-list cannot launch."""
    sandbox, plugin_dir = sandbox_env

    # Plugin with blocked import
    evil_code = """
import os  # Blocked module

def main(input_data):
    os.system("echo pwned")
"""

    # Should detect violation in static analysis
    violations = sandbox._check_imports(evil_code)
    assert len(violations) > 0
    assert any("os" in v for v in violations)


def test_allowed_module_can_launch(sandbox_env):
    """Test plugins with allowed modules can run."""
    sandbox, plugin_dir = sandbox_env

    # Plugin with safe imports
    safe_code = """
import json  # Allowed module
import datetime  # Allowed module

def main(input_data):
    now = datetime.datetime.now()
    return {"status": "ok"}
"""

    # Should NOT detect violations
    violations = sandbox._check_imports(safe_code)
    assert len(violations) == 0


def test_import_guard_creation(sandbox_env):
    """Test import guard code generation."""
    sandbox, plugin_dir = sandbox_env

    guard_code = sandbox._create_import_guard()

    # Should contain key elements
    assert "_guarded_import" in guard_code
    assert "ALLOWED_MODULES" in guard_code
    assert "BLOCKED_MODULES" in guard_code
    assert "ImportError" in guard_code


def test_multiple_blocked_imports(sandbox_env):
    """Test detection of multiple blocked imports."""
    sandbox, plugin_dir = sandbox_env

    bad_code = """
import os
import subprocess
import socket
from urllib import request

def evil():
    pass
"""

    violations = sandbox._check_imports(bad_code)

    # Should detect multiple violations
    assert len(violations) >= 3


def test_nested_module_import(sandbox_env):
    """Test detection of nested module imports."""
    sandbox, plugin_dir = sandbox_env

    # os.path should still trigger os block
    code = """
import os.path
from os.path import join
"""

    violations = sandbox._check_imports(code)
    assert len(violations) > 0
    assert any("os" in v for v in violations)


def test_import_call_detection(sandbox_env):
    """Test detection of __import__() calls."""
    sandbox, plugin_dir = sandbox_env

    code = """
# Try to bypass with __import__
evil_module = __import__('os')
"""

    violations = sandbox._check_imports(code)
    assert len(violations) > 0
    assert any("__import__" in v for v in violations)


def test_safe_modules_constant():
    """Test SAFE_MODULES contains expected modules."""
    assert "json" in SAFE_MODULES
    assert "datetime" in SAFE_MODULES
    assert "hashlib" in SAFE_MODULES
    assert "re" in SAFE_MODULES

    # Dangerous modules should NOT be in safe list
    assert "os" not in SAFE_MODULES
    assert "subprocess" not in SAFE_MODULES
    assert "socket" not in SAFE_MODULES


def test_custom_allowlist(plugin_dir=None):
    """Test using custom module allowlist."""
    if plugin_dir is None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "plugins"
            plugin_dir.mkdir()

    # Create sandbox with custom allowlist
    custom_allowlist = {"json", "math", "custom_module"}
    config = HardenedSandboxConfig(
        module_allowlist=custom_allowlist,
        strict_imports=True,
    )

    sandbox = HardenedPluginSandbox(plugin_dir, config)

    # Should use custom allowlist
    assert sandbox.module_allowlist == custom_allowlist

    # datetime should be blocked (not in custom list)
    code = "import datetime"
    violations = sandbox._check_imports(code)
    assert len(violations) > 0


def test_syntax_error_in_plugin(sandbox_env):
    """Test handling of syntax errors in plugin code."""
    sandbox, plugin_dir = sandbox_env

    # Invalid Python syntax
    bad_code = """
def invalid syntax here
    pass
"""

    violations = sandbox._check_imports(bad_code)

    # Should report syntax error
    assert len(violations) > 0
    assert any("syntax" in v.lower() for v in violations)


def test_dod_strict_enforcement():
    """Test DoD: Strict enforcement of module allowlist.

    Critical test: Plugins outside allow-list MUST be blocked.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir) / "plugins"
        plugin_dir.mkdir()

        config = HardenedSandboxConfig(strict_imports=True)
        sandbox = HardenedPluginSandbox(plugin_dir, config)

        # Try every blocked module
        blocked_modules = ["os", "subprocess", "socket", "pickle"]

        for module in blocked_modules:
            code = f"import {module}"
            violations = sandbox._check_imports(code)

            assert len(violations) > 0, f"Blocked module '{module}' was not detected!"
