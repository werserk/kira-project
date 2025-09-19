"""Ensure plugin entry points are importable and behave consistently."""
from __future__ import annotations

import importlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Tuple

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.plugin_sdk.context import PluginContext

PLUGINS_ROOT = Path(__file__).parent.parent.parent / "src" / "kira" / "plugins"


def iter_plugin_specs() -> Iterator[Tuple[str, str, Path, str]]:
    """Yield (module_name, function_name, src_dir, plugin_name)."""
    for manifest_path in sorted(PLUGINS_ROOT.glob("*/kira-plugin.json")):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        module_name, func_name = data["entry"].split(":", maxsplit=1)
        plugin_src = manifest_path.parent / "src"
        yield module_name, func_name, plugin_src, data["name"]


@contextmanager
def prepend_sys_path(path: Path) -> Iterator[None]:
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path.pop(0)


PLUGIN_SPECS = list(iter_plugin_specs())


@pytest.mark.parametrize(
    "module_name, func_name, plugin_src, plugin_name",
    PLUGIN_SPECS,
    ids=[spec[3] for spec in PLUGIN_SPECS],
)
def test_plugin_activate_returns_status(
    module_name: str, func_name: str, plugin_src: Path, plugin_name: str
) -> None:
    """Each plugin entry point should return a status payload."""
    with prepend_sys_path(plugin_src):
        module = importlib.import_module(module_name)

    activate = getattr(module, func_name)
    context = PluginContext(config={})
    result = activate(context)

    assert isinstance(result, dict)
    assert result.get("status") == "ok"
    assert result.get("plugin") == plugin_name
