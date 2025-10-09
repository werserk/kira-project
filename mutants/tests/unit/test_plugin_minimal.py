"""Minimal tests for built-in plugins as required by ADR-001."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Add plugin paths
plugins_root = src_path / "kira" / "plugins"
for plugin_dir in plugins_root.iterdir():
    if plugin_dir.is_dir():
        plugin_src_path = plugin_dir / "src"
        if plugin_src_path.exists():
            sys.path.insert(0, str(plugin_src_path.resolve()))


from kira.plugin_sdk.context import PluginContext


class TestPluginMinimal:
    """Minimal test suite for built-in plugins as required by ADR-001."""

    def test_inbox_plugin_can_be_imported(self) -> None:
        """Test that inbox plugin can be imported independently."""
        from kira_plugin_inbox.plugin import activate

        assert callable(activate)

    def test_calendar_plugin_can_be_imported(self) -> None:
        """Test that calendar plugin can be imported independently."""
        from kira_plugin_calendar.plugin import activate

        assert callable(activate)

    def test_deadlines_plugin_can_be_imported(self) -> None:
        """Test that deadlines plugin can be imported independently."""
        from kira_plugin_deadlines.plugin import activate

        assert callable(activate)

    def test_code_plugin_can_be_imported(self) -> None:
        """Test that code plugin can be imported independently."""
        from kira_plugin_code.plugin import activate

        assert callable(activate)

    def test_mailer_plugin_can_be_imported(self) -> None:
        """Test that mailer plugin can be imported independently."""
        from kira_plugin_mailer.plugin import activate

        assert callable(activate)

    def test_plugins_have_activate_function(self) -> None:
        """Test that all plugins have activate function with correct signature."""
        plugins = [
            "kira_plugin_inbox.plugin",
            "kira_plugin_calendar.plugin",
            "kira_plugin_deadlines.plugin",
            "kira_plugin_code.plugin",
            "kira_plugin_mailer.plugin",
        ]

        for plugin_module in plugins:
            module = __import__(plugin_module, fromlist=["activate"])
            activate_func = module.activate

            # Check that activate is callable
            assert callable(activate_func), f"Plugin {plugin_module} activate is not callable"

            # Check that activate accepts PluginContext
            import inspect

            sig = inspect.signature(activate_func)
            params = list(sig.parameters.keys())
            assert len(params) == 1, f"Plugin {plugin_module} activate should take 1 parameter, got {len(params)}"
            assert params[0] == "context", f"Plugin {plugin_module} activate first parameter should be 'context'"

    def test_plugins_return_dict_from_activate(self) -> None:
        """Test that all plugins return dict from activate function."""
        plugins = [
            "kira_plugin_inbox.plugin",
            "kira_plugin_calendar.plugin",
            "kira_plugin_deadlines.plugin",
            "kira_plugin_code.plugin",
            "kira_plugin_mailer.plugin",
        ]

        context = PluginContext(config={})

        for plugin_module in plugins:
            module = __import__(plugin_module, fromlist=["activate"])
            activate_func = module.activate

            # Call activate and check return type
            result = activate_func(context)
            assert isinstance(result, dict), f"Plugin {plugin_module} activate should return dict, got {type(result)}"
            assert "status" in result, f"Plugin {plugin_module} activate result should contain 'status' key"

    def test_plugin_manifests_are_valid(self) -> None:
        """Test that all plugin manifests are valid JSON and have required fields."""
        plugins_root = Path(__file__).parent.parent.parent / "src" / "kira" / "plugins"

        for plugin_dir in plugins_root.iterdir():
            if not plugin_dir.is_dir():
                continue

            manifest_path = plugin_dir / "kira-plugin.json"
            if not manifest_path.exists():
                continue

            # Load and validate JSON
            with open(manifest_path, encoding="utf-8") as f:
                manifest_data = json.load(f)

            # Check required fields
            required_fields = [
                "name",
                "version",
                "displayName",
                "description",
                "publisher",
                "engines",
                "permissions",
                "entry",
                "capabilities",
                "contributes",
            ]
            for field in required_fields:
                assert field in manifest_data, f"Plugin {plugin_dir.name} manifest missing required field: {field}"

            # Check that entry point is valid
            entry = manifest_data["entry"]
            assert ":" in entry, f"Plugin {plugin_dir.name} entry point should be in format 'module:function'"
            module_name, func_name = entry.split(":", 1)
            assert module_name.endswith("plugin"), f"Plugin {plugin_dir.name} entry module should end with 'plugin'"
            assert func_name == "activate", f"Plugin {plugin_dir.name} entry function should be 'activate'"
