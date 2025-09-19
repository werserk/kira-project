"""Static import boundary checks for built-in plugins."""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

PLUGINS_ROOT = Path(__file__).parent.parent.parent / "src" / "kira" / "plugins"


def iter_plugin_modules() -> Iterator[Tuple[str, Path]]:
    """Yield (plugin_slug, python_file_path) for all plugin modules."""
    for plugin_dir in sorted(PLUGINS_ROOT.iterdir()):
        if not plugin_dir.is_dir():
            continue
        slug = plugin_dir.name
        package_dir = plugin_dir / "src"
        if not package_dir.exists():
            continue
        for path in package_dir.rglob("*.py"):
            yield slug, path


def is_private_core_import(module_name: str) -> bool:
    """Return True if module points to a private core module."""
    if not module_name.startswith("kira.core"):
        return False
    parts = module_name.split(".")[2:]  # skip kira.core
    return any(part.startswith("_") for part in parts)


def test_plugins_do_not_cross_import() -> None:
    """Plugins must not import other plugin packages or private core modules."""
    violations: List[str] = []
    plugin_packages: Dict[str, str] = {
        slug: f"kira_plugin_{slug.replace('-', '_')}" for slug, _ in iter_plugin_modules()
    }

    for slug, module_path in iter_plugin_modules():
        package_name = plugin_packages[slug]
        tree = ast.parse(module_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if module_name.startswith("kira_plugin_") and not module_name.startswith(package_name):
                        violations.append(
                            f"{module_path}: imports another plugin package '{module_name}'"
                        )
                    if module_name.startswith("kira.plugins"):
                        violations.append(
                            f"{module_path}: imports from core plugins namespace '{module_name}'"
                        )
                    if is_private_core_import(module_name):
                        violations.append(
                            f"{module_path}: imports private core module '{module_name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.module is None:
                    # Relative import within the package is allowed
                    continue
                module_name = node.module or ""
                if module_name.startswith("kira_plugin_") and not module_name.startswith(package_name):
                    violations.append(
                        f"{module_path}: from-imports another plugin package '{module_name}'"
                    )
                if module_name.startswith("kira.plugins"):
                    violations.append(
                        f"{module_path}: from-imports core plugins namespace '{module_name}'"
                    )
                if is_private_core_import(module_name):
                    violations.append(
                        f"{module_path}: from-imports private core module '{module_name}'"
                    )

    assert not violations, "\n".join(violations)
