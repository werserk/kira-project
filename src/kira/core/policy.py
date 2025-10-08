"""Policy enforcement for plugin permissions and sandbox controls.

This module implements the permission model defined in ADR-004, checking whether
plugins are allowed to perform specific operations based on their manifest
permissions and sandbox configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "PermissionDeniedError",
    "Policy",
    "PolicyViolation",
    "SandboxConfig",
    "check_fs_access",
    "check_permission",
]


class PermissionDeniedError(Exception):
    """Raised when a plugin attempts an operation without required permissions."""

    def __init__(self, permission: str, reason: str = "") -> None:
        self.permission = permission
        self.reason = reason
        msg = f"Permission denied: {permission}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


@dataclass
class PolicyViolation:
    """Details about a policy violation."""

    permission: str
    reason: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class SandboxConfig:
    """Sandbox configuration from plugin manifest."""

    strategy: str = "subprocess"
    timeout_ms: int = 30000
    memory_limit_mb: int | None = None
    network_access: bool = False
    fs_read_paths: list[str] = field(default_factory=list)
    fs_write_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> SandboxConfig:
        """Create SandboxConfig from plugin manifest."""
        sandbox_section = manifest.get("sandbox", {})
        fs_access = sandbox_section.get("fsAccess", {})

        return cls(
            strategy=sandbox_section.get("strategy", "subprocess"),
            timeout_ms=sandbox_section.get("timeoutMs", 30000),
            memory_limit_mb=sandbox_section.get("memoryLimit"),
            network_access=sandbox_section.get("networkAccess", False),
            fs_read_paths=fs_access.get("read", []),
            fs_write_paths=fs_access.get("write", []),
        )


@dataclass
class Policy:
    """Policy encapsulating granted permissions and sandbox settings."""

    plugin_name: str
    granted_permissions: list[str]
    sandbox_config: SandboxConfig
    vault_path: Path | None = None

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any], vault_path: Path | None = None) -> Policy:
        """Create Policy from plugin manifest.

        Parameters
        ----------
        manifest
            Plugin manifest dictionary
        vault_path
            Path to vault (for FS access checks)

        Returns
        -------
        Policy
            Policy instance with permissions and sandbox config
        """
        return cls(
            plugin_name=manifest.get("name", "unknown"),
            granted_permissions=manifest.get("permissions", []),
            sandbox_config=SandboxConfig.from_manifest(manifest),
            vault_path=vault_path,
        )

    def check_permission(self, permission: str, *, context: dict[str, Any] | None = None) -> None:
        """Check if permission is granted, raise PermissionDeniedError if not.

        Parameters
        ----------
        permission
            Permission name to check (e.g., "net", "vault.write")
        context
            Optional context for detailed checks

        Raises
        ------
        PermissionDeniedError
            If permission is not granted
        """
        if permission not in self.granted_permissions:
            reason = f"Plugin '{self.plugin_name}' lacks permission '{permission}'"
            if context:
                reason += f" (context: {context})"
            raise PermissionDeniedError(permission, reason)

    def check_network_access(self) -> None:
        """Check if network access is allowed.

        Raises
        ------
        PermissionDeniedError
            If network permission is not granted or sandbox doesn't allow it
        """
        if "net" not in self.granted_permissions:
            raise PermissionDeniedError("net", "Network access not granted in manifest")

        if not self.sandbox_config.network_access:
            raise PermissionDeniedError("net", "Network access disabled in sandbox configuration")

    def check_fs_read_access(self, path: str | Path) -> None:
        """Check if filesystem read access to path is allowed.

        Parameters
        ----------
        path
            Path to check access for

        Raises
        ------
        PermissionDeniedError
            If fs.read permission not granted or path not whitelisted
        """
        if "fs.read" not in self.granted_permissions:
            raise PermissionDeniedError("fs.read", f"Cannot read {path}")

        # Check if path is within allowed prefixes
        path_obj = Path(path).resolve()

        # Vault paths are forbidden by default (ADR-006)
        if self.vault_path and self._is_within_path(path_obj, self.vault_path):
            raise PermissionDeniedError(
                "fs.read",
                f"Direct Vault access forbidden (path: {path}). Use Host API instead.",
            )

        # Check whitelist
        if not self._check_path_in_allowlist(path_obj, self.sandbox_config.fs_read_paths):
            raise PermissionDeniedError(
                "fs.read",
                f"Path {path} not in read allowlist: {self.sandbox_config.fs_read_paths}",
            )

    def check_fs_write_access(self, path: str | Path) -> None:
        """Check if filesystem write access to path is allowed.

        Parameters
        ----------
        path
            Path to check access for

        Raises
        ------
        PermissionDeniedError
            If fs.write permission not granted or path not whitelisted
        """
        if "fs.write" not in self.granted_permissions:
            raise PermissionDeniedError("fs.write", f"Cannot write to {path}")

        path_obj = Path(path).resolve()

        # Vault paths are strictly forbidden for direct writes (ADR-006)
        if self.vault_path and self._is_within_path(path_obj, self.vault_path):
            raise PermissionDeniedError(
                "fs.write",
                f"Direct Vault writes forbidden (path: {path}). Use Host API instead.",
            )

        # Check whitelist
        if not self._check_path_in_allowlist(path_obj, self.sandbox_config.fs_write_paths):
            raise PermissionDeniedError(
                "fs.write",
                f"Path {path} not in write allowlist: {self.sandbox_config.fs_write_paths}",
            )

    def _check_path_in_allowlist(self, path: Path, allowlist: Sequence[str]) -> bool:
        """Check if path is within any allowed prefix."""
        if not allowlist:
            return False

        for allowed_prefix in allowlist:
            allowed_path = Path(allowed_prefix).resolve()
            if self._is_within_path(path, allowed_path):
                return True
        return False

    @staticmethod
    def _is_within_path(path: Path, parent: Path) -> bool:
        """Check if path is within parent directory."""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def get_violations(self) -> list[PolicyViolation]:
        """Check policy for potential issues and return violations.

        Returns
        -------
        list[PolicyViolation]
            List of policy violations or warnings
        """
        violations: list[PolicyViolation] = []

        # Check for overly permissive configurations
        if "net" in self.granted_permissions and not self.sandbox_config.network_access:
            violations.append(
                PolicyViolation(
                    permission="net",
                    reason="Permission granted but sandbox network_access is False",
                )
            )

        # Check for conflicting FS permissions
        if "fs.write" in self.granted_permissions and not self.sandbox_config.fs_write_paths:
            violations.append(
                PolicyViolation(
                    permission="fs.write",
                    reason="Write permission granted but no write paths configured",
                )
            )

        if "fs.read" in self.granted_permissions and not self.sandbox_config.fs_read_paths:
            violations.append(
                PolicyViolation(
                    permission="fs.read",
                    reason="Read permission granted but no read paths configured",
                )
            )

        return violations


def check_permission(permission: str, granted_permissions: Sequence[str], plugin_name: str = "unknown") -> None:
    """Standalone helper to check if permission is granted.

    Parameters
    ----------
    permission
        Permission to check
    granted_permissions
        List of granted permissions
    plugin_name
        Name of plugin (for error messages)

    Raises
    ------
    PermissionDeniedError
        If permission not granted
    """
    if permission not in granted_permissions:
        raise PermissionDeniedError(permission, f"Plugin '{plugin_name}' lacks permission '{permission}'")


def check_fs_access(
    path: str | Path,
    mode: str,
    allowlist: Sequence[str],
    vault_path: Path | None = None,
) -> None:
    """Standalone helper to check filesystem access.

    Parameters
    ----------
    path
        Path to check
    mode
        Access mode: 'read' or 'write'
    allowlist
        List of allowed path prefixes
    vault_path
        Vault path (to forbid direct access per ADR-006)

    Raises
    ------
    PermissionDeniedError
        If access not allowed
    """
    path_obj = Path(path).resolve()

    # Check vault access (ADR-006)
    if vault_path:
        try:
            path_obj.relative_to(vault_path.resolve())
            raise PermissionDeniedError(
                f"fs.{mode}",
                f"Direct Vault {mode} forbidden (path: {path}). Use Host API instead.",
            )
        except ValueError:
            pass  # Not within vault, continue checks

    # Check allowlist
    if not allowlist:
        raise PermissionDeniedError(f"fs.{mode}", f"No {mode} paths configured in allowlist")

    for allowed_prefix in allowlist:
        try:
            path_obj.relative_to(Path(allowed_prefix).resolve())
            return  # Access allowed
        except ValueError:
            continue

    raise PermissionDeniedError(f"fs.{mode}", f"Path {path} not in {mode} allowlist: {allowlist}")
