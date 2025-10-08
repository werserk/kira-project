"""Permission constants and helpers for plugin authors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

PermissionName = Literal[
    "calendar.read",
    "calendar.write",
    "vault.read",
    "vault.write",
    "fs.read",
    "fs.write",
    "net",
    "secrets.read",
    "secrets.write",
    "events.publish",
    "events.subscribe",
    "scheduler.create",
    "scheduler.cancel",
    "sandbox.execute",
]
"""Literal union of supported permission identifiers."""

ALL_PERMISSIONS: tuple[PermissionName, ...] = (
    "calendar.read",
    "calendar.write",
    "vault.read",
    "vault.write",
    "fs.read",
    "fs.write",
    "net",
    "secrets.read",
    "secrets.write",
    "events.publish",
    "events.subscribe",
    "scheduler.create",
    "scheduler.cancel",
    "sandbox.execute",
)
"""Tuple containing every permission understood by the host."""

_PERMISSION_DESCRIPTIONS: dict[PermissionName, str] = {
    "calendar.read": "Read access to calendars managed by the host.",
    "calendar.write": "Write access to calendars managed by the host.",
    "vault.read": "Read secrets from the secure vault.",
    "vault.write": "Write secrets to the secure vault.",
    "fs.read": "Read-only access to whitelisted filesystem paths.",
    "fs.write": "Write access to whitelisted filesystem paths.",
    "net": "Outbound network access from the sandbox.",
    "secrets.read": "Read plugin-scoped secrets using the secrets manager.",
    "secrets.write": "Store plugin-scoped secrets using the secrets manager.",
    "events.publish": "Publish domain events to the host bus.",
    "events.subscribe": "Subscribe to domain events emitted by the host.",
    "scheduler.create": "Create scheduled jobs via the scheduler facade.",
    "scheduler.cancel": "Cancel jobs previously scheduled by the plugin.",
    "sandbox.execute": "Request execution in the isolated sandbox.",
}

__all__ = [
    "ALL_PERMISSIONS",
    "PermissionName",
    "describe",
    "ensure_permissions",
    "requires",
]


def describe(permission: PermissionName) -> str:
    """Return a human readable description for ``permission``."""

    return _PERMISSION_DESCRIPTIONS[permission]


def requires(permission: PermissionName, granted: Sequence[str]) -> bool:
    """Return ``True`` if ``permission`` is present in ``granted``."""

    return permission in granted


def ensure_permissions(
    required: Iterable[PermissionName],
    granted: Sequence[str],
) -> set[PermissionName]:
    """Return the subset of ``required`` permissions that are missing."""

    granted_set = set(granted)
    return {permission for permission in required if permission not in granted_set}
