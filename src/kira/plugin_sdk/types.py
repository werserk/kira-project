"""Typed contracts shared across the Plugin SDK.

The module centralises public type aliases and protocols that plugin authors
can rely on without importing from private engine modules.

Example:
    from collections.abc import Mapping
    from kira.plugin_sdk import types

    def handle_event(context: "types.PluginContext", payload: types.EventPayload) -> None:
        context.logger.info(f"Received payload keys: {list(payload or {})}")
"""

from __future__ import annotations

from collections.abc import Awaitable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

if TYPE_CHECKING:  # pragma: no cover - imported only for typing
    from .context import PluginContext

PayloadT = TypeVar("PayloadT", bound=Mapping[str, Any] | None, contravariant=True)
ReturnT = TypeVar("ReturnT", covariant=True)

EventPayload = Mapping[str, Any] | None
"""Standard payload type delivered to event handlers."""

CommandArguments = Mapping[str, Any] | None
"""Arguments passed to command handlers."""

PluginState = MutableMapping[str, Any]
"""Mutable storage available to plugins, typically backed by key/value stores."""


class EventHandler(Protocol[PayloadT]):
    """Callable interface for event handlers.

    Handlers accept a :class:`PluginContext` and optional payload. They may
    either return ``None`` or an awaitable. The engine is responsible for
    awaiting returned coroutines.
    """

    def __call__(
        self,
        context: "PluginContext",
        payload: PayloadT,
    ) -> Awaitable[None] | None:
        """Execute the handler with the provided context and payload."""


class CommandHandler(Protocol[PayloadT, ReturnT]):
    """Callable interface for command handlers invoked by the host."""

    def __call__(
        self,
        context: "PluginContext",
        arguments: PayloadT,
    ) -> Awaitable[ReturnT] | ReturnT:
        """Execute the command and optionally return a value."""


@dataclass(slots=True)
class RPCRequest:
    """Container describing an outbound RPC request from a plugin."""

    method: str
    payload: Mapping[str, Any] | None = None
    timeout: float | None = None


@dataclass(slots=True)
class RPCResponse:
    """Container describing the host response to an RPC request."""

    result: Mapping[str, Any] | None
    status: str = "ok"


__all__ = [
    "CommandArguments",
    "CommandHandler",
    "EventHandler",
    "EventPayload",
    "PluginState",
    "RPCRequest",
    "RPCResponse",
]
