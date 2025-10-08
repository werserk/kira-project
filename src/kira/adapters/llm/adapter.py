"""LLM Adapter protocol and base types.

Defines the interface for LLM providers with support for:
- generate(): Single-turn text completion
- chat(): Multi-turn conversation
- tool_call(): Function calling with structured output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

__all__ = [
    "LLMAdapter",
    "LLMResponse",
    "Message",
    "Tool",
    "ToolCall",
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
]


class LLMError(Exception):
    """Base exception for LLM operations."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    pass


@dataclass
class Message:
    """Chat message."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass
class Tool:
    """Tool definition for function calling."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    """Tool call from LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    finish_reason: Literal["stop", "length", "tool_calls", "error"] = "stop"
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)


class LLMAdapter(Protocol):
    """Protocol for LLM adapters.

    All LLM providers must implement this interface.
    """

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0,
    ) -> LLMResponse:
        """Generate text completion from prompt.

        Parameters
        ----------
        prompt
            Input prompt
        model
            Model name (provider-specific)
        temperature
            Sampling temperature (0.0-2.0)
        max_tokens
            Maximum tokens to generate
        timeout
            Request timeout in seconds

        Returns
        -------
        LLMResponse
            Generated response

        Raises
        ------
        LLMError
            On API errors
        LLMTimeoutError
            On timeout
        LLMRateLimitError
            On rate limit
        """
        ...

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0,
    ) -> LLMResponse:
        """Multi-turn chat conversation.

        Parameters
        ----------
        messages
            List of conversation messages
        model
            Model name (provider-specific)
        temperature
            Sampling temperature (0.0-2.0)
        max_tokens
            Maximum tokens to generate
        timeout
            Request timeout in seconds

        Returns
        -------
        LLMResponse
            Generated response

        Raises
        ------
        LLMError
            On API errors
        LLMTimeoutError
            On timeout
        LLMRateLimitError
            On rate limit
        """
        ...

    def tool_call(
        self,
        messages: list[Message],
        tools: list[Tool],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """Chat with tool/function calling support.

        Parameters
        ----------
        messages
            List of conversation messages
        tools
            Available tools for LLM to call
        model
            Model name (provider-specific)
        temperature
            Sampling temperature (0.0-2.0)
        max_tokens
            Maximum tokens to generate
        timeout
            Request timeout in seconds

        Returns
        -------
        LLMResponse
            Response with potential tool calls

        Raises
        ------
        LLMError
            On API errors
        LLMTimeoutError
            On timeout
        LLMRateLimitError
            On rate limit
        """
        ...
