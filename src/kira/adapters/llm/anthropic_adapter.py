"""Anthropic (Claude) LLM adapter implementation.

Direct Anthropic API integration for Claude models.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .adapter import LLMError, LLMRateLimitError, LLMResponse, LLMTimeoutError, Message, Tool, ToolCall

__all__ = ["AnthropicAdapter"]


class AnthropicAdapter:
    """Anthropic API adapter.

    Supports Claude models through official Anthropic API.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.anthropic.com/v1",
        default_model: str = "claude-3-5-sonnet-20241022",
        api_version: str = "2023-06-01",
    ) -> None:
        """Initialize Anthropic adapter.

        Parameters
        ----------
        api_key
            Anthropic API key
        base_url
            API base URL
        default_model
            Default model to use
        api_version
            API version header
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.api_version = api_version

    def _make_headers(self) -> dict[str, str]:
        """Create request headers."""
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }

    def _messages_to_anthropic(self, messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
        """Convert Message objects to Anthropic format.

        Returns
        -------
        tuple[str, list[dict]]
            (system_prompt, messages_list)
        """
        system_prompt = ""
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                anthropic_messages.append({"role": msg.role, "content": msg.content})

        return system_prompt, anthropic_messages

    def _tools_to_anthropic(self, tools: list[Tool]) -> list[dict[str, Any]]:
        """Convert Tool objects to Anthropic format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    def _parse_response(self, response_data: dict[str, Any]) -> LLMResponse:
        """Parse API response to LLMResponse."""
        content_blocks = response_data.get("content", [])

        # Extract text content
        text_content = ""
        tool_calls = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        finish_reason = response_data.get("stop_reason", "end_turn")
        if tool_calls:
            finish_reason = "tool_calls"

        usage = response_data.get("usage", {})

        return LLMResponse(
            content=text_content,
            finish_reason=finish_reason,  # type: ignore
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
            model=response_data.get("model", ""),
            raw_response=response_data,
        )

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0,
    ) -> LLMResponse:
        """Generate text completion from prompt."""
        messages = [Message(role="user", content=prompt)]
        return self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout)

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0,
    ) -> LLMResponse:
        """Multi-turn chat conversation."""
        model = model or self.default_model

        system_prompt, anthropic_messages = self._messages_to_anthropic(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/messages",
                    headers=self._make_headers(),
                    json=payload,
                )

            if response.status_code == 429:
                raise LLMRateLimitError("Anthropic rate limit exceeded")

            if response.status_code >= 400:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except Exception:
                    pass
                raise LLMError(f"Anthropic API error ({response.status_code}): {error_msg}")

            response_data = response.json()
            return self._parse_response(response_data)

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Anthropic request timed out after {timeout}s") from e
        except (httpx.HTTPError, httpx.RequestError) as e:
            raise LLMError(f"Anthropic HTTP error: {e}") from e

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
        """Chat with tool/function calling support."""
        model = model or self.default_model

        system_prompt, anthropic_messages = self._messages_to_anthropic(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "tools": self._tools_to_anthropic(tools),
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/messages",
                    headers=self._make_headers(),
                    json=payload,
                )

            if response.status_code == 429:
                raise LLMRateLimitError("Anthropic rate limit exceeded")

            if response.status_code >= 400:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except Exception:
                    pass
                raise LLMError(f"Anthropic API error ({response.status_code}): {error_msg}")

            response_data = response.json()
            return self._parse_response(response_data)

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Anthropic request timed out after {timeout}s") from e
        except (httpx.HTTPError, httpx.RequestError) as e:
            raise LLMError(f"Anthropic HTTP error: {e}") from e
