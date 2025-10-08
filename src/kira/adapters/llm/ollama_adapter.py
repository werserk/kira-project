"""Ollama local LLM adapter implementation.

Provides local fallback when remote providers are unavailable.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .adapter import LLMError, LLMRateLimitError, LLMResponse, LLMTimeoutError, Message, Tool, ToolCall

__all__ = ["OllamaAdapter"]


class OllamaAdapter:
    """Ollama local API adapter.

    Supports local models through Ollama REST API.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama2",
    ) -> None:
        """Initialize Ollama adapter.

        Parameters
        ----------
        base_url
            Ollama API base URL
        default_model
            Default model to use
        """
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def _messages_to_prompt(self, messages: list[Message]) -> str:
        """Convert messages to a single prompt string."""
        prompt_parts = []
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")
        return "\n\n".join(prompt_parts)

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
        model = model or self.default_model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )

            if response.status_code >= 400:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
                raise LLMError(f"Ollama API error ({response.status_code}): {error_msg}")

            response_data = response.json()
            content = response_data.get("response", "")

            return LLMResponse(
                content=content,
                finish_reason="stop",
                usage={
                    "prompt_tokens": response_data.get("prompt_eval_count", 0),
                    "completion_tokens": response_data.get("eval_count", 0),
                    "total_tokens": response_data.get("prompt_eval_count", 0)
                    + response_data.get("eval_count", 0),
                },
                model=model,
                raw_response=response_data,
            )

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Ollama request timed out after {timeout}s") from e
        except httpx.ConnectError as e:
            raise LLMError(f"Ollama not available: {e}") from e
        except (httpx.HTTPError, httpx.RequestError) as e:
            raise LLMError(f"Ollama HTTP error: {e}") from e

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
        # Convert messages to prompt
        prompt = self._messages_to_prompt(messages)
        prompt += "\n\nAssistant:"
        return self.generate(prompt, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout)

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

        Note: Ollama doesn't natively support tool calling, so we include
        tool descriptions in the prompt and expect JSON responses.
        """
        # Build tool descriptions
        tools_desc = "Available tools:\n"
        for tool in tools:
            tools_desc += f"- {tool.name}: {tool.description}\n"

        # Add tools to system message
        enhanced_messages = messages.copy()
        if enhanced_messages and enhanced_messages[0].role == "system":
            enhanced_messages[0] = Message(
                role="system",
                content=enhanced_messages[0].content + "\n\n" + tools_desc + "\n\nRespond with valid JSON.",
            )
        else:
            enhanced_messages.insert(
                0,
                Message(role="system", content=tools_desc + "\n\nRespond with valid JSON."),
            )

        return self.chat(enhanced_messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
