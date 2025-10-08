"""OpenRouter LLM adapter implementation.

Provides access to multiple LLM providers through OpenRouter API.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .adapter import LLMError, LLMRateLimitError, LLMResponse, LLMTimeoutError, Message, Tool, ToolCall

__all__ = ["OpenRouterAdapter"]


class OpenRouterAdapter:
    """OpenRouter API adapter.

    Supports multiple models through unified API.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        default_model: str = "anthropic/claude-3.5-sonnet",
        site_url: str | None = None,
        site_name: str | None = None,
    ) -> None:
        """Initialize OpenRouter adapter.

        Parameters
        ----------
        api_key
            OpenRouter API key
        base_url
            API base URL
        default_model
            Default model to use
        site_url
            Optional site URL for rankings
        site_name
            Optional site name for rankings
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.site_url = site_url
        self.site_name = site_name

    def _make_headers(self) -> dict[str, str]:
        """Create request headers."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers

    def _messages_to_dict(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert Message objects to API format."""
        result = []
        for msg in messages:
            msg_dict: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            result.append(msg_dict)
        return result

    def _tools_to_dict(self, tools: list[Tool]) -> list[dict[str, Any]]:
        """Convert Tool objects to API format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def _parse_response(self, response_data: dict[str, Any]) -> LLMResponse:
        """Parse API response to LLMResponse."""
        choices = response_data.get("choices", [])
        if not choices:
            raise LLMError("No choices in response")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        finish_reason = choice.get("finish_reason", "stop")

        # Parse tool calls if present
        tool_calls_data = message.get("tool_calls", [])
        tool_calls = []
        for tc in tool_calls_data:
            function = tc.get("function", {})
            try:
                arguments = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}

            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=function.get("name", ""),
                    arguments=arguments,
                )
            )

        usage = response_data.get("usage", {})

        return LLMResponse(
            content=content,
            finish_reason=finish_reason,  # type: ignore
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
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
        return self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

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

        payload = {
            "model": model,
            "messages": self._messages_to_dict(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._make_headers(),
                    json=payload,
                )

            if response.status_code == 429:
                raise LLMRateLimitError("OpenRouter rate limit exceeded")

            if response.status_code >= 400:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except Exception:
                    pass
                raise LLMError(f"OpenRouter API error ({response.status_code}): {error_msg}")

            response_data = response.json()
            return self._parse_response(response_data)

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"OpenRouter request timed out after {timeout}s") from e
        except (httpx.HTTPError, httpx.RequestError) as e:
            raise LLMError(f"OpenRouter HTTP error: {e}") from e

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

        payload = {
            "model": model,
            "messages": self._messages_to_dict(messages),
            "tools": self._tools_to_dict(tools),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._make_headers(),
                    json=payload,
                )

            if response.status_code == 429:
                raise LLMRateLimitError("OpenRouter rate limit exceeded")

            if response.status_code >= 400:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except Exception:
                    pass
                raise LLMError(f"OpenRouter API error ({response.status_code}): {error_msg}")

            response_data = response.json()
            return self._parse_response(response_data)

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"OpenRouter request timed out after {timeout}s") from e
        except (httpx.HTTPError, httpx.RequestError) as e:
            raise LLMError(f"OpenRouter HTTP error: {e}") from e
