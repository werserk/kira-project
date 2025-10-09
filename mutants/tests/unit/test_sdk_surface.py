"""Tests for plugin SDK surface stability and completeness."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.plugin_sdk import context, decorators, manifest, permissions, rpc, types


class TestSDKSurfaceStability:
    """Test that SDK surface is stable and complete."""

    def test_plugin_sdk_exports_expected_modules(self) -> None:
        """Test that plugin_sdk exports all expected modules."""
        import kira.plugin_sdk as sdk

        expected_modules = {
            "context",
            "decorators",
            "manifest",
            "permissions",
            "rpc",
            "types",
        }

        actual_modules = {name for name in dir(sdk) if not name.startswith("_")}
        assert expected_modules.issubset(actual_modules), f"Missing modules: {expected_modules - actual_modules}"

    def test_context_module_has_expected_exports(self) -> None:
        """Test that context module exports expected classes and functions."""
        expected_exports = {
            "PluginContext",
            "EventBus",
            "Logger",
            "Scheduler",
            "KeyValueStore",
            "SecretsManager",
        }

        actual_exports = {name for name in dir(context) if not name.startswith("_")}
        assert expected_exports.issubset(
            actual_exports
        ), f"Missing context exports: {expected_exports - actual_exports}"

    def test_decorators_module_has_expected_exports(self) -> None:
        """Test that decorators module exports expected decorators."""
        expected_exports = {
            "on_event",
            "command",
            "permission",
            "timeout",
            "retry",
        }

        actual_exports = {name for name in dir(decorators) if not name.startswith("_")}
        assert expected_exports.issubset(
            actual_exports
        ), f"Missing decorator exports: {expected_exports - actual_exports}"

    def test_manifest_module_has_expected_exports(self) -> None:
        """Test that manifest module exports expected functions."""
        expected_exports = {
            "PluginManifestValidator",
            "validate_plugin_manifest",
            "get_manifest_schema",
        }

        actual_exports = {name for name in dir(manifest) if not name.startswith("_")}
        assert expected_exports.issubset(
            actual_exports
        ), f"Missing manifest exports: {expected_exports - actual_exports}"

    def test_permissions_module_has_expected_exports(self) -> None:
        """Test that permissions module exports expected functions and constants."""
        expected_exports = {
            "PermissionName",
            "ALL_PERMISSIONS",
            "describe",
            "requires",
            "ensure_permissions",
        }

        actual_exports = {name for name in dir(permissions) if not name.startswith("_")}
        assert expected_exports.issubset(
            actual_exports
        ), f"Missing permissions exports: {expected_exports - actual_exports}"

    def test_rpc_module_has_expected_exports(self) -> None:
        """Test that rpc module exports expected classes."""
        expected_exports = {
            "RPCError",
            "HostRPCClient",
            "Transport",
        }

        actual_exports = {name for name in dir(rpc) if not name.startswith("_")}
        assert expected_exports.issubset(actual_exports), f"Missing rpc exports: {expected_exports - actual_exports}"

    def test_types_module_has_expected_exports(self) -> None:
        """Test that types module exports expected types and protocols."""
        expected_exports = {
            "EventPayload",
            "CommandArguments",
            "PluginState",
            "EventHandler",
            "CommandHandler",
            "RPCRequest",
            "RPCResponse",
        }

        actual_exports = {name for name in dir(types) if not name.startswith("_")}
        assert expected_exports.issubset(actual_exports), f"Missing types exports: {expected_exports - actual_exports}"

    def test_plugin_context_signature_stability(self) -> None:
        """Test that PluginContext has stable signature."""
        from kira.plugin_sdk.context import PluginContext

        # Check constructor signature
        sig = inspect.signature(PluginContext.__init__)
        expected_params = {"config"}
        actual_params = set(sig.parameters.keys())

        # Should have at least the expected parameters
        assert expected_params.issubset(
            actual_params
        ), f"Missing PluginContext params: {expected_params - actual_params}"

    def test_decorator_signatures_are_callable(self) -> None:
        """Test that decorators are callable with expected signatures."""
        from kira.plugin_sdk.decorators import command, on_event, permission

        # Test on_event decorator
        assert callable(on_event)
        sig = inspect.signature(on_event)
        assert "event_name" in sig.parameters

        # Test command decorator
        assert callable(command)
        sig = inspect.signature(command)
        assert "command_name" in sig.parameters

        # Test permission decorator
        assert callable(permission)
        sig = inspect.signature(permission)
        assert "perm" in sig.parameters

    def test_manifest_validator_has_expected_methods(self) -> None:
        """Test that PluginManifestValidator has expected methods."""
        from kira.plugin_sdk.manifest import PluginManifestValidator

        expected_methods = {
            "validate_manifest",
            "validate_manifest_file",
        }

        actual_methods = {name for name in dir(PluginManifestValidator) if not name.startswith("_")}
        assert expected_methods.issubset(
            actual_methods
        ), f"Missing validator methods: {expected_methods - actual_methods}"

    def test_sdk_modules_have_docstrings(self) -> None:
        """Test that all SDK modules have docstrings."""
        modules = [context, decorators, manifest, permissions, rpc, types]

        for module in modules:
            assert module.__doc__ is not None, f"Module {module.__name__} missing docstring"
            assert len(module.__doc__.strip()) > 10, f"Module {module.__name__} has too short docstring"

    def test_sdk_classes_have_type_hints(self) -> None:
        """Test that SDK classes have proper type hints."""
        from kira.plugin_sdk.context import PluginContext
        from kira.plugin_sdk.manifest import PluginManifestValidator

        # Check that methods have type hints
        for name, method in inspect.getmembers(PluginContext, predicate=inspect.ismethod):
            if not name.startswith("_"):
                sig = inspect.signature(method)
                for param_name, param in sig.parameters.items():
                    if param_name != "self":
                        assert (
                            param.annotation != inspect.Parameter.empty
                        ), f"Parameter {param_name} in {name} missing type hint"

        for name, method in inspect.getmembers(PluginManifestValidator, predicate=inspect.ismethod):
            if not name.startswith("_"):
                sig = inspect.signature(method)
                for param_name, param in sig.parameters.items():
                    if param_name != "self":
                        assert (
                            param.annotation != inspect.Parameter.empty
                        ), f"Parameter {param_name} in {name} missing type hint"
