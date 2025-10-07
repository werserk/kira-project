"""Plugin loading and activation system with version checking."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from packaging import version

from ..plugin_sdk.context import PluginContext
from ..plugin_sdk.manifest import PluginManifestValidator
from .policy import Policy
from .sandbox import Sandbox


class PluginLoadError(Exception):
    """Raised when plugin loading fails."""

    pass


class PluginVersionError(PluginLoadError):
    """Raised when plugin version is incompatible."""

    pass


class PluginLoader:
    """Loads and activates plugins with version checking and sandbox support."""

    def __init__(
        self,
        context: PluginContext | None = None,
        sandbox: Sandbox | None = None,
        vault_path: Path | None = None,
        use_sandbox: bool = True,
    ) -> None:
        """Initialize the plugin loader.

        Parameters
        ----------
        context
            Plugin context to pass to activated plugins. If None, a default
            context will be created.
        sandbox
            Sandbox instance for plugin isolation. If None and use_sandbox=True,
            a default sandbox will be created.
        vault_path
            Path to vault (for policy enforcement). If None, policy checks
            won't enforce vault path restrictions.
        use_sandbox
            Whether to use sandbox for subprocess strategy plugins.
        """
        self.context = context or PluginContext()
        self.manifest_validator = PluginManifestValidator()
        self.vault_path = vault_path
        self.use_sandbox = use_sandbox
        self.sandbox = sandbox if sandbox is not None else (Sandbox() if use_sandbox else None)
        self._loaded_plugins: dict[str, dict[str, Any]] = {}

    def load_plugin(self, plugin_path: Path) -> dict[str, Any]:
        """Load a plugin from the specified path.

        Parameters
        ----------
        plugin_path
            Path to the plugin directory containing kira-plugin.json

        Returns
        -------
        dict[str, Any]
            Plugin metadata and activation result

        Raises
        ------
        PluginLoadError
            If plugin loading fails
        PluginVersionError
            If plugin version is incompatible
        """
        manifest_path = plugin_path / "kira-plugin.json"
        if not manifest_path.exists():
            raise PluginLoadError(f"Plugin manifest not found: {manifest_path}")

        # Load and validate manifest
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise PluginLoadError(f"Failed to load manifest: {e}") from e

        # Validate manifest structure
        if not self.manifest_validator.validate_manifest(manifest):
            raise PluginLoadError("Invalid plugin manifest")

        # Check engine compatibility
        self._check_engine_compatibility(manifest)

        # Load plugin module
        plugin_name = manifest["name"]
        entry_point = manifest.get("entry", f"{plugin_name}.plugin:activate")

        try:
            module_name, func_name = entry_point.split(":", 1)
            module = self._load_plugin_module(plugin_path, module_name)
            activate_func = getattr(module, func_name)
        except (ImportError, AttributeError) as e:
            raise PluginLoadError(f"Failed to load plugin entry point: {e}") from e

        # Activate plugin
        try:
            result = activate_func(self.context)
        except Exception as e:
            raise PluginLoadError(f"Plugin activation failed: {e}") from e

        # Store plugin info
        plugin_info = {
            "name": plugin_name,
            "version": manifest.get("version", "unknown"),
            "path": str(plugin_path),
            "manifest": manifest,
            "result": result,
        }
        self._loaded_plugins[plugin_name] = plugin_info

        return plugin_info

    def _check_engine_compatibility(self, manifest: dict[str, Any]) -> None:
        """Check if plugin is compatible with current engine version.

        Parameters
        ----------
        manifest
            Plugin manifest dictionary

        Raises
        ------
        PluginVersionError
            If plugin version is incompatible
        """
        engines = manifest.get("engines", {})
        required_version = engines.get("kira")

        if not required_version:
            # No version requirement specified, assume compatible
            return

        # Get current engine version (this would be set by the host)
        current_version = getattr(sys.modules.get("kira"), "__version__", "0.1.0")

        try:
            # Check if current version satisfies requirement
            if not self._version_satisfies(current_version, required_version):
                raise PluginVersionError(
                    f"Plugin requires Kira {required_version}, but current version is {current_version}"
                )
        except version.InvalidVersion as e:
            raise PluginVersionError(f"Invalid version specification: {e}") from e

    def _version_satisfies(self, current: str, required: str) -> bool:
        """Check if current version satisfies the required version spec.

        Parameters
        ----------
        current
            Current version string
        required
            Required version specification (e.g., ">=1.0.0,<2.0.0")

        Returns
        -------
        bool
            True if current version satisfies the requirement
        """
        current_ver = version.parse(current)

        # Handle simple version specs like "^1.0.0" or ">=1.0.0"
        if required.startswith("^"):
            # Caret range: compatible within same major version
            base_version = version.parse(required[1:])
            return current_ver >= base_version and current_ver < version.parse(f"{base_version.major + 1}.0.0")
        if required.startswith("~"):
            # Tilde range: compatible within same minor version
            base_version = version.parse(required[1:])
            return (
                current_ver >= base_version
                and current_ver < version.parse(f"{base_version.major}.{base_version.minor + 1}.0")
            )
        # Use packaging's version specifier
        from packaging.specifiers import SpecifierSet
        spec = SpecifierSet(required)
        return current_ver in spec

    def _load_plugin_module(self, plugin_path: Path, module_name: str) -> Any:
        """Load a plugin module from the specified path.

        Parameters
        ----------
        plugin_path
            Path to the plugin directory
        module_name
            Name of the module to load

        Returns
        -------
        Any
            Loaded module

        Raises
        ------
        ImportError
            If module cannot be imported
        """
        # Add plugin src directory to Python path
        src_path = plugin_path / "src"
        if src_path.exists():
            sys.path.insert(0, str(src_path))
            try:
                return importlib.import_module(module_name)
            finally:
                # Remove from path to avoid conflicts
                if str(src_path) in sys.path:
                    sys.path.remove(str(src_path))
        else:
            # Try loading from plugin directory directly
            sys.path.insert(0, str(plugin_path))
            try:
                return importlib.import_module(module_name)
            finally:
                if str(plugin_path) in sys.path:
                    sys.path.remove(str(plugin_path))

    def get_loaded_plugins(self) -> dict[str, dict[str, Any]]:
        """Get information about all loaded plugins.

        Returns
        -------
        dict[str, dict[str, Any]]
            Dictionary mapping plugin names to their metadata
        """
        return self._loaded_plugins.copy()

    def is_plugin_loaded(self, plugin_name: str) -> bool:
        """Check if a plugin is currently loaded.

        Parameters
        ----------
        plugin_name
            Name of the plugin to check

        Returns
        -------
        bool
            True if plugin is loaded
        """
        return plugin_name in self._loaded_plugins

    def load_plugin_in_sandbox(
        self,
        plugin_path: Path,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        """Load a plugin in subprocess sandbox (ADR-004).

        Parameters
        ----------
        plugin_path
            Path to plugin directory
        manifest
            Plugin manifest dictionary

        Returns
        -------
        dict[str, Any]
            Plugin metadata and activation result

        Raises
        ------
        PluginLoadError
            If sandbox launch fails
        """
        if not self.sandbox:
            raise PluginLoadError("Sandbox not initialized")

        plugin_name = manifest["name"]
        entry_point = manifest.get("entry", f"{plugin_name}.plugin:activate")

        # Create policy from manifest
        policy = Policy.from_manifest(manifest, vault_path=self.vault_path)

        # Check for policy violations
        violations = policy.get_violations()
        if violations:
            for violation in violations:
                print(
                    f"Warning: Policy violation in {plugin_name}: "
                    f"{violation.permission} - {violation.reason}"
                )

        # Launch in sandbox
        try:
            plugin_process = self.sandbox.launch(
                plugin_name=plugin_name,
                entry_point=entry_point,
                plugin_path=plugin_path,
                policy=policy,
                context_config=dict(self.context.config) if self.context.config else None,
            )
        except Exception as exc:
            raise PluginLoadError(
                f"Failed to launch {plugin_name} in sandbox: {exc}"
            ) from exc

        # Store plugin info
        plugin_info = {
            "name": plugin_name,
            "version": manifest.get("version", "unknown"),
            "path": str(plugin_path),
            "manifest": manifest,
            "sandbox": True,
            "process": plugin_process,
            "policy": policy,
        }
        self._loaded_plugins[plugin_name] = plugin_info

        return plugin_info

    def should_use_sandbox(self, manifest: dict[str, Any]) -> bool:
        """Determine if plugin should be loaded in sandbox.

        Parameters
        ----------
        manifest
            Plugin manifest

        Returns
        -------
        bool
            True if plugin should use sandbox
        """
        if not self.use_sandbox:
            return False

        sandbox_config = manifest.get("sandbox", {})
        strategy = sandbox_config.get("strategy", "subprocess")

        return bool(strategy == "subprocess")

    def cleanup(self) -> None:
        """Clean up resources (stop sandbox processes).

        Should be called when loader is no longer needed.
        """
        if self.sandbox:
            self.sandbox.stop_all()
