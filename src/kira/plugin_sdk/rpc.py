"""JSON-RPC 2.0 implementation for plugin-host communication.

This module implements JSON-RPC 2.0 over stdio with Content-Length framing
as specified in ADR-004. Plugins use this to communicate with the host process
when running in subprocess sandbox mode.
"""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .types import RPCRequest, RPCResponse

Transport = Callable[[RPCRequest], RPCResponse]
"""Type alias for RPC transports supplied by the host."""

__all__ = [
    "HostRPCClient",
    "JSONRPCError",
    "JSONRPCMessage",
    "RPCError",
    "StdioTransport",
    "Transport",
    "parse_jsonrpc_message",
    "serialize_jsonrpc_message",
]


class RPCError(RuntimeError):
    """Raised when the host returns an error response."""

    def __init__(self, message: str, code: int = -1, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class JSONRPCError(Exception):
    """Raised for JSON-RPC protocol errors."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    def __init__(self, message: str, code: int, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-RPC error object."""
        error: dict[str, Any] = {"code": self.code, "message": str(self)}
        if self.data is not None:
            error["data"] = self.data
        return error


@dataclass
class JSONRPCMessage:
    """JSON-RPC 2.0 message container.

    Represents either a request, response, or error following the JSON-RPC 2.0 spec.
    """

    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str | None = None
    params: dict[str, Any] | list[Any] | None = None
    result: Any = None
    error: dict[str, Any] | None = None

    def is_request(self) -> bool:
        """Check if this is a request message."""
        return self.method is not None

    def is_response(self) -> bool:
        """Check if this is a response message."""
        return self.method is None and (self.result is not None or self.error is not None)

    def is_notification(self) -> bool:
        """Check if this is a notification (request without id)."""
        return self.method is not None and self.id is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        msg: dict[str, Any] = {"jsonrpc": self.jsonrpc}

        if self.id is not None:
            msg["id"] = self.id

        if self.method is not None:
            msg["method"] = self.method
            if self.params is not None:
                msg["params"] = self.params
        elif self.result is not None:
            msg["result"] = self.result
        elif self.error is not None:
            msg["error"] = self.error

        return msg


def serialize_jsonrpc_message(message: JSONRPCMessage) -> bytes:
    """Serialize JSON-RPC message with Content-Length framing.

    Parameters
    ----------
    message
        Message to serialize

    Returns
    -------
    bytes
        Serialized message with Content-Length header
    """
    content = json.dumps(message.to_dict(), ensure_ascii=False)
    content_bytes = content.encode("utf-8")
    header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
    return header.encode("ascii") + content_bytes


def parse_jsonrpc_message(data: bytes) -> JSONRPCMessage:
    """Parse JSON-RPC message from bytes.

    Parameters
    ----------
    data
        Raw message data (may include Content-Length header)

    Returns
    -------
    JSONRPCMessage
        Parsed message

    Raises
    ------
    JSONRPCError
        If message is malformed
    """
    # Strip Content-Length header if present
    if data.startswith(b"Content-Length:"):
        parts = data.split(b"\r\n\r\n", 1)
        if len(parts) != 2:
            raise JSONRPCError("Invalid Content-Length framing", JSONRPCError.PARSE_ERROR)
        data = parts[1]

    try:
        obj = json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise JSONRPCError(f"Invalid JSON: {exc}", JSONRPCError.PARSE_ERROR) from exc

    if not isinstance(obj, dict):
        raise JSONRPCError("Message must be an object", JSONRPCError.INVALID_REQUEST)

    if obj.get("jsonrpc") != "2.0":
        raise JSONRPCError("Invalid jsonrpc version", JSONRPCError.INVALID_REQUEST)

    return JSONRPCMessage(
        jsonrpc=obj["jsonrpc"],
        id=obj.get("id"),
        method=obj.get("method"),
        params=obj.get("params"),
        result=obj.get("result"),
        error=obj.get("error"),
    )


class StdioTransport:
    """JSON-RPC transport over stdin/stdout.

    Used by plugins running in subprocess sandbox to communicate with the host.
    Messages are framed with Content-Length headers as per Language Server Protocol.
    """

    def __init__(self, input_stream: Any = None, output_stream: Any = None) -> None:
        """Initialize stdio transport.

        Parameters
        ----------
        input_stream
            Input stream (default: sys.stdin.buffer)
        output_stream
            Output stream (default: sys.stdout.buffer)
        """
        self.input = input_stream or sys.stdin.buffer
        self.output = output_stream or sys.stdout.buffer

    def send(self, message: JSONRPCMessage) -> None:
        """Send a JSON-RPC message.

        Parameters
        ----------
        message
            Message to send
        """
        data = serialize_jsonrpc_message(message)
        self.output.write(data)
        self.output.flush()

    def receive(self) -> JSONRPCMessage:
        """Receive a JSON-RPC message.

        Returns
        -------
        JSONRPCMessage
            Received message

        Raises
        ------
        JSONRPCError
            If message is malformed
        EOFError
            If stream is closed
        """
        # Read Content-Length header
        header_line = self.input.readline()
        if not header_line:
            raise EOFError("Input stream closed")

        if not header_line.startswith(b"Content-Length:"):
            raise JSONRPCError(
                f"Expected Content-Length header, got: {header_line!r}",
                JSONRPCError.PARSE_ERROR,
            )

        try:
            content_length = int(header_line.decode("ascii").split(":")[1].strip())
        except (ValueError, IndexError) as exc:
            raise JSONRPCError(f"Invalid Content-Length: {header_line!r}", JSONRPCError.PARSE_ERROR) from exc

        # Read empty line
        empty_line = self.input.readline()
        if empty_line != b"\r\n":
            raise JSONRPCError(
                f"Expected empty line after header, got: {empty_line!r}",
                JSONRPCError.PARSE_ERROR,
            )

        # Read content
        content = self.input.read(content_length)
        if len(content) != content_length:
            raise JSONRPCError(
                f"Expected {content_length} bytes, got {len(content)}",
                JSONRPCError.PARSE_ERROR,
            )

        return parse_jsonrpc_message(content)

    def call(self, request: RPCRequest) -> RPCResponse:
        """Send request and receive response.

        Parameters
        ----------
        request
            RPC request

        Returns
        -------
        RPCResponse
            Response from host
        """
        # Generate request ID
        request_id = str(uuid.uuid4())

        # Create JSON-RPC request
        message = JSONRPCMessage(
            jsonrpc="2.0",
            id=request_id,
            method=request.method,
            params=dict(request.payload) if request.payload else None,
        )

        # Send request
        self.send(message)

        # Receive response
        response = self.receive()

        # Validate response
        if response.id != request_id:
            raise JSONRPCError(
                f"Response ID mismatch: expected {request_id}, got {response.id}",
                JSONRPCError.INTERNAL_ERROR,
            )

        if response.error:
            error_data = response.error
            raise RPCError(
                error_data.get("message", "Unknown error"),
                code=error_data.get("code", -1),
                data=error_data.get("data"),
            )

        return RPCResponse(result=response.result, status="ok")


class HostRPCClient:
    """RPC client for plugins to communicate with the host.

    Uses the provided transport (typically StdioTransport in subprocess mode)
    to send JSON-RPC requests to the host.

    Example:
        >>> from kira.plugin_sdk.rpc import HostRPCClient, StdioTransport
        >>> client = HostRPCClient(transport=StdioTransport())
        >>> result = client.call("vault.read", {"entity_id": "task-123"})
    """

    def __init__(self, transport: Transport | StdioTransport) -> None:
        """Initialize RPC client.

        Parameters
        ----------
        transport
            Transport for communication with host
        """
        self._transport = transport

    def call(
        self,
        method: str,
        payload: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Mapping[str, Any] | None:
        """Invoke method on the host with the supplied payload.

        Parameters
        ----------
        method
            RPC method name (e.g., "vault.read", "events.publish")
        payload
            Method parameters
        timeout
            Optional timeout in seconds

        Returns
        -------
        dict or None
            Method result

        Raises
        ------
        RPCError
            If the host returns an error
        """
        request = RPCRequest(method=method, payload=payload, timeout=timeout)

        # Call transport
        if isinstance(self._transport, StdioTransport):
            response = self._transport.call(request)
        else:
            # Legacy callable transport
            response = self._transport(request)

        if response.status != "ok":
            raise RPCError(f"Host RPC failed with status '{response.status}'")

        return response.result
