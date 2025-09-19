"""Tests for the plugin scaffolding utilities."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.cli.kira_plugin_template import (
    PluginTemplateOptions,
    build_manifest,
    create_plugin_scaffold,
    main,
    slugify,
)


def test_slugify_normalizes_names() -> None:
    assert slugify("My Fancy Plugin") == "my-fancy-plugin"
    assert slugify("my_plugin") == "my-plugin"

    with pytest.raises(ValueError):
        slugify("!!!")


def test_build_manifest_generates_expected_entry() -> None:
    options = PluginTemplateOptions(
        slug="demo",
        display_name="Demo",
        description="Demo plugin",
        publisher="kira",
        permissions=["events.publish"],
        capabilities=["pull"],
        events=["demo.started"],
        commands=["demo.run"],
        output_dir=Path("."),
    )

    manifest = build_manifest(options)
    assert manifest["name"] == "kira-demo"
    assert manifest["entry"] == "kira_plugin_demo.plugin:activate"
    assert manifest["permissions"] == ["events.publish"]


def test_create_plugin_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    options = PluginTemplateOptions(
        slug="example",
        display_name="Example",
        description="Example plugin",
        publisher="kira",
        permissions=["events.publish"],
        capabilities=["pull"],
        events=["example.started"],
        commands=["example.run"],
        output_dir=tmp_path,
    )

    plugin_root = create_plugin_scaffold(options)
    manifest_path = plugin_root / "kira-plugin.json"
    package_root = plugin_root / "src" / "kira_plugin_example"
    test_path = Path("tests") / "plugins" / "example" / "test_plugin.py"

    assert manifest_path.exists()
    assert (package_root / "__init__.py").exists()
    assert (package_root / "plugin.py").exists()
    assert test_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["name"] == "kira-example"


def test_cli_create_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = Path("plugins")

    exit_code = main([
        "create",
        "Sample Plugin",
        "--output-dir",
        str(output_dir),
        "--permissions",
        "events.publish",
        "--capabilities",
        "notify",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "kira-sample-plugin" in captured.out

    manifest_path = output_dir / "sample-plugin" / "kira-plugin.json"
    assert manifest_path.exists()
