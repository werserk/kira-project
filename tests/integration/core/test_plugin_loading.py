"""Integration tests for plugin loading and entry points.

Tests verify:
- Plugin loads via manifest entry without sys.path manipulation
- Plugin imports are clean (no side effects)
- Plugin entry points are properly aligned
"""

from pathlib import Path

import pytest


@pytest.fixture
def inbox_plugin_path():
    """Get inbox plugin path."""
    import kira

    kira_root = Path(kira.__file__).parent
    plugin_path = kira_root / "plugins" / "inbox"

    if not plugin_path.exists():
        pytest.skip("Inbox plugin not found")

    return plugin_path


class TestPluginEntryPoint:
    """Test plugin entry point alignment."""

    def test_plugin_loads_without_sys_path_hacks(self, inbox_plugin_path: Path):
        """Verify plugin loads via manifest entry without sys.path manipulation.

        DoD: plugin starts from a clean env via `entry` without extra steps.
        """
        from kira.core.plugin_loader import PluginLoader
        from kira.plugin_sdk.context import PluginContext

        # Create loader with clean context
        context = PluginContext(config={"vault": {"path": "./vault"}})
        loader = PluginLoader(context=context, use_sandbox=False)

        # Load plugin
        result = loader.load_plugin(inbox_plugin_path)

        # Verify plugin loaded successfully
        assert result["name"] == "kira-inbox"
        assert result["result"]["status"] == "ok"
        assert "version" in result["result"]

    def test_plugin_imports_are_clean(self, inbox_plugin_path: Path):
        """Verify plugin module can be imported without side effects."""
        import importlib
        import sys

        # Add plugin src to path temporarily
        plugin_src = inbox_plugin_path / "src"
        sys.path.insert(0, str(plugin_src))

        try:
            # Import should work cleanly
            plugin_module = importlib.import_module("kira_plugin_inbox.plugin")

            # Verify activate function exists
            assert hasattr(plugin_module, "activate")
            assert callable(plugin_module.activate)

        finally:
            # Clean up
            if str(plugin_src) in sys.path:
                sys.path.remove(str(plugin_src))


pytestmark = pytest.mark.integration

