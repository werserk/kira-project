"""Stable public surface for Kira plugin authors.

The :mod:`kira.plugin_sdk` package re-exports the supported modules defined
in ADR-002. Plugin authors should only import from this namespace to remain
compatible with future engine versions.

Example:
    >>> from kira.plugin_sdk import decorators
    >>> @decorators.command("ping")
    ... def ping(context, **_):
    ...     context.logger.info("pong")
"""

from . import context, decorators, manifest, permissions, rpc, types

__all__ = [
    "context",
    "decorators",
    "manifest",
    "permissions",
    "rpc",
    "types",
]
