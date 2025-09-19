"""Validation tests for built-in plugin manifests."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.plugin_sdk.manifest import PluginManifestValidator

PLUGINS_ROOT = Path(__file__).parent.parent.parent / "src" / "kira" / "plugins"


def iter_manifest_paths() -> Iterator[Path]:
    """Yield paths to all plugin manifest files."""
    for manifest in sorted(PLUGINS_ROOT.glob("*/kira-plugin.json")):
        yield manifest


@pytest.mark.parametrize("manifest_path", list(iter_manifest_paths()), ids=lambda p: p.parent.name)
def test_plugin_manifests_are_valid(manifest_path: Path) -> None:
    """All plugin manifests must satisfy the shared schema."""
    validator = PluginManifestValidator()
    errors = validator.validate_manifest_file(str(manifest_path))
    assert errors == [], f"Manifest {manifest_path} has validation errors: {errors}"


def test_manifest_matches_scaffold_structure() -> None:
    """Each plugin should expose the expected scaffold layout."""
    validator = PluginManifestValidator()
    for manifest_path in iter_manifest_paths():
        plugin_dir = manifest_path.parent
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        slug = plugin_dir.name
        expected_name = f"kira-{slug}"
        assert data["name"] == expected_name

        package_name = f"kira_plugin_{slug.replace('-', '_')}"
        package_root = plugin_dir / "src" / package_name
        assert package_root.exists(), f"Missing package directory for {expected_name}"
        assert (package_root / "__init__.py").exists()
        assert (package_root / "plugin.py").exists()

        # Ensure manifest is still valid to guard against skew
        errors = validator.validate_manifest_file(str(manifest_path))
        assert errors == []
