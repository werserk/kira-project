"""Thin RPC facade used by plugins to communicate with the host."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .types import RPCRequest, RPCResponse

Transport = Callable[[RPCRequest], RPCResponse]
"""Type alias for RPC transports supplied by the host."""

__all__ = ["RPCError", "HostRPCClient", "Transport"]


class RPCError(RuntimeError):
    """Raised when the host returns an error response."""


class HostRPCClient:
    """Minimal RPC client that delegates to a host-provided transport.

    Example:
        >>> from kira.plugin_sdk.rpc import HostRPCClient, RPCResponse
        >>> def echo_transport(request):
        ...     return RPCResponse(result={"method": request.method})
        >>> client = HostRPCClient(transport=echo_transport)
        >>> client.call("ping")
        {'method': 'ping'}
    """

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def call(
        self,
        method: str,
        payload: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Mapping[str, Any] | None:
        """Invoke ``method`` on the host with the supplied ``payload``."""

        request = RPCRequest(method=method, payload=payload, timeout=timeout)
        response = self._transport(request)

        if response.status != "ok":
            raise RPCError(f"Host RPC failed with status '{response.status}'")

        return response.result
