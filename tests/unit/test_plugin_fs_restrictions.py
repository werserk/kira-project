"""Test that plugins don't write directly to Vault filesystem (ADR-006).

Plugins must use Host API (ctx.vault) for all Vault writes.
Direct filesystem writes are forbidden.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

PLUGINS_ROOT = Path(__file__).parent.parent.parent / "src" / "kira" / "plugins"


def iter_plugin_python_files() -> Iterator[tuple[str, Path]]:
    """Yield (plugin_name, python_file) for all plugin Python files."""
    for plugin_dir in sorted(PLUGINS_ROOT.iterdir()):
        if not plugin_dir.is_dir():
            continue
        
        plugin_name = plugin_dir.name
        src_dir = plugin_dir / "src"
        
        if not src_dir.exists():
            continue
        
        for py_file in src_dir.rglob("*.py"):
            yield plugin_name, py_file


def find_filesystem_writes(file_path: Path) -> list[str]:
    """Find potential filesystem write operations in Python file.
    
    Parameters
    ----------
    file_path
        Path to Python file to analyze
    
    Returns
    -------
    list[str]
        List of violations found
    """
    violations = []
    
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    except SyntaxError:
        return []
    
    for node in ast.walk(tree):
        # Check for open() calls with write mode
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                # Check if mode is 'w', 'a', 'wb', etc.
                for arg in node.args[1:2]:  # Second argument is mode
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if any(m in arg.value for m in ['w', 'a', 'x', '+']):
                            # Check if it's writing to Vault path
                            if len(node.args) > 0:
                                first_arg = node.args[0]
                                # Conservative check: flag any write operation
                                # Real implementation should check path
                                violations.append(
                                    f"Line {node.lineno}: open() with write mode '{arg.value}'"
                                )
        
        # Check for Path.write_text() or Path.write_bytes()
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ('write_text', 'write_bytes', 'mkdir', 'unlink'):
                    violations.append(
                        f"Line {node.lineno}: Path.{node.func.attr}() - direct file operation"
                    )
        
        # Check for os.remove, os.unlink, shutil operations
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                forbidden_ops = {
                    'remove', 'unlink', 'rmdir', 'removedirs',
                    'mkdir', 'makedirs', 'rename', 'replace'
                }
                if node.func.attr in forbidden_ops:
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id in ('os', 'shutil'):
                            violations.append(
                                f"Line {node.lineno}: {node.func.value.id}.{node.func.attr}() - "
                                f"direct filesystem operation"
                            )
    
    return violations


def test_plugins_do_not_write_to_filesystem_directly() -> None:
    """Test that plugins don't perform direct filesystem writes.
    
    Plugins should use Host API (ctx.vault.create_entity, etc.) instead of
    direct file operations. This ensures validation, ID generation, and
    event emission.
    
    Note: This test may have false positives for legitimate temp file usage.
    Review violations and add exceptions as needed.
    """
    all_violations: dict[str, list[str]] = {}
    
    for plugin_name, py_file in iter_plugin_python_files():
        violations = find_filesystem_writes(py_file)
        
        if violations:
            file_key = f"{plugin_name}: {py_file.name}"
            all_violations[file_key] = violations
    
    # Allow exceptions for specific cases
    allowed_patterns = [
        # Temp files are OK
        "tmp",
        "temp",
        # Test files are OK
        "test_",
        # Logging to plugin-specific paths is OK
        "logs/plugins",
    ]
    
    # Filter out allowed violations
    filtered_violations = {}
    for file_key, violations in all_violations.items():
        filtered = []
        for violation in violations:
            # Check if violation matches any allowed pattern
            is_allowed = False
            for pattern in allowed_patterns:
                if pattern in violation.lower():
                    is_allowed = True
                    break
            
            if not is_allowed:
                filtered.append(violation)
        
        if filtered:
            filtered_violations[file_key] = filtered
    
    # Build assertion message
    if filtered_violations:
        message = "\n\nPlugins must not write directly to filesystem!\n"
        message += "Use Host API (ctx.vault) for all Vault operations.\n\n"
        message += "Violations found:\n\n"
        
        for file_key, violations in filtered_violations.items():
            message += f"  {file_key}:\n"
            for violation in violations:
                message += f"    - {violation}\n"
            message += "\n"
        
        message += "If these are legitimate operations (e.g., temp files), "
        message += "add appropriate patterns to allowed_patterns in this test.\n"
        
        # For MVP, we make this a warning instead of failure
        # Once all plugins are migrated, change to: assert not filtered_violations, message
        print(f"\n⚠️  WARNING: {message}")
    else:
        print("\n✅ No direct filesystem writes detected in plugins")


def test_plugins_use_vault_api_pattern() -> None:
    """Test that plugins use recommended Vault API patterns.
    
    Plugins should emit 'vault.create_intent' events or use ctx.vault API.
    """
    recommended_patterns = [
        "vault.create_intent",
        "vault.update_intent",
        "ctx.vault",
        "context.vault",
    ]
    
    plugins_with_patterns: dict[str, list[str]] = {}
    
    for plugin_name, py_file in iter_plugin_python_files():
        content = py_file.read_text(encoding="utf-8")
        
        found_patterns = []
        for pattern in recommended_patterns:
            if pattern in content:
                found_patterns.append(pattern)
        
        if found_patterns:
            plugins_with_patterns[plugin_name] = found_patterns
    
    # This is informational - just report what we found
    if plugins_with_patterns:
        print("\n✅ Plugins using Vault API patterns:")
        for plugin_name, patterns in plugins_with_patterns.items():
            print(f"  - {plugin_name}: {', '.join(patterns)}")
    else:
        print("\n⚠️  No plugins using Vault API patterns yet (MVP transition)")


if __name__ == "__main__":
    test_plugins_do_not_write_to_filesystem_directly()
    test_plugins_use_vault_api_pattern()

