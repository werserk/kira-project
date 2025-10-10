"""Multi-provider LLM router with fallback support.

Routes requests to appropriate providers based on task type.
Implements fallback to local Ollama when remote providers fail.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Literal

from ...observability.loguru_config import get_logger, timing_context

from .adapter import LLMAdapter, LLMError, LLMRateLimitError, LLMResponse, LLMTimeoutError, Message, Tool
from .anthropic_adapter import AnthropicAdapter
from .ollama_adapter import OllamaAdapter
from .openai_adapter import OpenAIAdapter
from .openrouter_adapter import OpenRouterAdapter

# Loguru logger for LLM operations
llm_logger = get_logger("langgraph")

__all__ = ["LLMRouter", "TaskType", "RouterConfig", "LLMErrorEnhanced"]


class TaskType(Enum):
    """Task types for routing decisions."""

    PLANNING = "planning"  # Complex planning tasks
    STRUCTURING = "structuring"  # JSON structuring tasks
    DEFAULT = "default"  # General tasks


class LLMErrorEnhanced(LLMError):
    """Enhanced LLM error with retry information."""

    def __init__(
        self,
        message: str,
        *,
        error_type: str = "unknown",
        provider: str = "unknown",
        retryable: bool = False,
    ) -> None:
        """Initialize enhanced error.

        Parameters
        ----------
        message
            Error message
        error_type
            Type of error
        provider
            Provider name
        retryable
            Whether error is retryable
        """
        super().__init__(message)
        self.error_type = error_type
        self.provider = provider
        self.retryable = retryable


class RouterConfig:
    """Configuration for LLM router."""

    def __init__(
        self,
        *,
        planning_provider: str = "anthropic",
        structuring_provider: str = "openai",
        default_provider: str = "openrouter",
        enable_ollama_fallback: bool = True,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
        backoff_multiplier: float = 2.0,
    ) -> None:
        """Initialize router configuration.

        Parameters
        ----------
        planning_provider
            Provider for planning tasks
        structuring_provider
            Provider for structuring tasks
        default_provider
            Default provider
        enable_ollama_fallback
            Enable fallback to Ollama
        max_retries
            Maximum retry attempts
        initial_backoff
            Initial backoff delay in seconds
        max_backoff
            Maximum backoff delay in seconds
        backoff_multiplier
            Backoff multiplier
        """
        self.planning_provider = planning_provider
        self.structuring_provider = structuring_provider
        self.default_provider = default_provider
        self.enable_ollama_fallback = enable_ollama_fallback
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier


class LLMRouter:
    """Routes LLM requests to appropriate providers with fallback."""

    def __init__(
        self,
        config: RouterConfig,
        *,
        anthropic_adapter: AnthropicAdapter | None = None,
        openai_adapter: OpenAIAdapter | None = None,
        openrouter_adapter: OpenRouterAdapter | None = None,
        ollama_adapter: OllamaAdapter | None = None,
    ) -> None:
        """Initialize router.

        Parameters
        ----------
        config
            Router configuration
        anthropic_adapter
            Anthropic adapter instance
        openai_adapter
            OpenAI adapter instance
        openrouter_adapter
            OpenRouter adapter instance
        ollama_adapter
            Ollama adapter instance
        """
        self.config = config
        self.adapters: dict[str, LLMAdapter | None] = {
            "anthropic": anthropic_adapter,
            "openai": openai_adapter,
            "openrouter": openrouter_adapter,
            "ollama": ollama_adapter,
        }

    def _get_provider_for_task(self, task_type: TaskType) -> str:
        """Get provider name for task type."""
        if task_type == TaskType.PLANNING:
            return self.config.planning_provider
        elif task_type == TaskType.STRUCTURING:
            return self.config.structuring_provider
        else:
            return self.config.default_provider

    def _get_adapter(self, provider: str) -> LLMAdapter:
        """Get adapter for provider.

        Raises
        ------
        LLMErrorEnhanced
            If adapter not configured
        """
        adapter = self.adapters.get(provider)
        if adapter is None:
            raise LLMErrorEnhanced(
                f"Provider {provider} not configured",
                error_type="configuration",
                provider=provider,
                retryable=False,
            )
        return adapter

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0,
        task_type: TaskType = TaskType.DEFAULT,
    ) -> LLMResponse:
        """Generate text completion from prompt.

        Routes to default provider.

        Parameters
        ----------
        prompt
            Input prompt
        model
            Optional model override
        temperature
            Sampling temperature
        max_tokens
            Maximum tokens
        timeout
            Request timeout
        task_type
            Task type for routing

        Returns
        -------
        LLMResponse
            Generated response

        Raises
        ------
        LLMErrorEnhanced
            If request fails
        """
        provider = self._get_provider_for_task(task_type)

        with timing_context(
            "llm_generate",
            component="langgraph",
            provider=provider,
            task_type=task_type.value,
            prompt_length=len(prompt),
            max_tokens=max_tokens,
        ) as ctx:
            try:
                adapter = self._get_adapter(provider)
                response = self._execute_with_retry(
                    adapter,
                    "generate",
                    provider,
                    prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )

                # Add response metrics to context
                if hasattr(response, 'usage'):
                    ctx['completion_tokens'] = getattr(response.usage, 'completion_tokens', 0)
                    ctx['prompt_tokens'] = getattr(response.usage, 'prompt_tokens', 0)
                    ctx['total_tokens'] = getattr(response.usage, 'total_tokens', 0)

                llm_logger.info(
                    "LLM generation completed",
                    provider=provider,
                    task_type=task_type.value,
                    prompt_length=len(prompt),
                    response_length=len(response.content),
                )

                return response

        except LLMErrorEnhanced as e:
            # Try Ollama fallback if enabled and error is retryable
            if self.config.enable_ollama_fallback and e.retryable:
                ollama = self.adapters.get("ollama")
                if ollama:
                    try:
                        return ollama.generate(
                            prompt,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=timeout,
                        )
                    except Exception:
                        # Re-raise original error if fallback also fails
                        pass
            raise

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.config.initial_backoff * (self.config.backoff_multiplier ** (attempt - 1))
        return min(delay, self.config.max_backoff)

    def _execute_with_retry(
        self,
        adapter: LLMAdapter,
        method: str,
        provider: str,
        *args: Any,
        **kwargs: Any,
    ) -> LLMResponse:
        """Execute adapter method with retry logic.

        Parameters
        ----------
        adapter
            Adapter instance
        method
            Method name to call
        provider
            Provider name for error reporting
        *args
            Method positional arguments
        **kwargs
            Method keyword arguments

        Returns
        -------
        LLMResponse
            Response from adapter

        Raises
        ------
        LLMErrorEnhanced
            If all retries fail
        """
        last_error = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                method_func = getattr(adapter, method)
                return method_func(*args, **kwargs)

            except LLMRateLimitError as e:
                last_error = LLMErrorEnhanced(
                    str(e),
                    error_type="rate_limit",
                    provider=provider,
                    retryable=True,
                )
                if attempt < self.config.max_retries:
                    delay = self._calculate_backoff(attempt)
                    time.sleep(delay)
                    continue

            except LLMTimeoutError as e:
                last_error = LLMErrorEnhanced(
                    str(e),
                    error_type="timeout",
                    provider=provider,
                    retryable=True,
                )
                if attempt < self.config.max_retries:
                    delay = self._calculate_backoff(attempt)
                    time.sleep(delay)
                    continue

            except LLMError as e:
                # Check if it's a network error (retryable)
                if "connection" in str(e).lower() or "network" in str(e).lower():
                    last_error = LLMErrorEnhanced(
                        str(e),
                        error_type="network",
                        provider=provider,
                        retryable=True,
                    )
                    if attempt < self.config.max_retries:
                        delay = self._calculate_backoff(attempt)
                        time.sleep(delay)
                        continue
                else:
                    last_error = LLMErrorEnhanced(
                        str(e),
                        error_type="api_error",
                        provider=provider,
                        retryable=False,
                    )
                    break

        # If we get here, all retries failed
        if last_error:
            raise last_error
        raise LLMErrorEnhanced(
            "Unknown error during execution",
            error_type="unknown",
            provider=provider,
            retryable=False,
        )

    def chat(
        self,
        messages: list[Message],
        *,
        task_type: TaskType = TaskType.DEFAULT,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0,
    ) -> LLMResponse:
        """Route chat request to appropriate provider.

        Parameters
        ----------
        messages
            Chat messages
        task_type
            Type of task for routing
        model
            Optional model override
        temperature
            Sampling temperature
        max_tokens
            Maximum tokens
        timeout
            Request timeout

        Returns
        -------
        LLMResponse
            Response from provider

        Raises
        ------
        LLMErrorEnhanced
            If request fails
        """
        provider = self._get_provider_for_task(task_type)

        # Calculate total message length
        total_message_length = sum(len(msg.get('content', '')) for msg in messages if isinstance(msg, dict))

        with timing_context(
            "llm_chat",
            component="langgraph",
            provider=provider,
            task_type=task_type.value,
            num_messages=len(messages),
            total_message_length=total_message_length,
            max_tokens=max_tokens,
        ) as ctx:
            try:
                adapter = self._get_adapter(provider)
                response = self._execute_with_retry(
                    adapter,
                    "chat",
                    provider,
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )

                # Add response metrics to context
                if hasattr(response, 'usage'):
                    ctx['completion_tokens'] = getattr(response.usage, 'completion_tokens', 0)
                    ctx['prompt_tokens'] = getattr(response.usage, 'prompt_tokens', 0)
                    ctx['total_tokens'] = getattr(response.usage, 'total_tokens', 0)

                llm_logger.info(
                    "LLM chat completed",
                    provider=provider,
                    task_type=task_type.value,
                    num_messages=len(messages),
                    response_length=len(response.content),
                )

                return response

        except LLMErrorEnhanced as e:
            # Try Ollama fallback if enabled and error is retryable
            if self.config.enable_ollama_fallback and e.retryable:
                ollama = self.adapters.get("ollama")
                if ollama:
                    try:
                        return ollama.chat(
                            messages,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=timeout,
                        )
                    except Exception as fallback_error:
                        # Re-raise original error if fallback also fails
                        pass
            raise

    def tool_call(
        self,
        messages: list[Message],
        tools: list[Tool],
        *,
        task_type: TaskType = TaskType.DEFAULT,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """Route tool call request to appropriate provider.

        Parameters
        ----------
        messages
            Chat messages
        tools
            Available tools
        task_type
            Type of task for routing
        model
            Optional model override
        temperature
            Sampling temperature
        max_tokens
            Maximum tokens
        timeout
            Request timeout

        Returns
        -------
        LLMResponse
            Response from provider

        Raises
        ------
        LLMErrorEnhanced
            If request fails
        """
        provider = self._get_provider_for_task(task_type)

        try:
            adapter = self._get_adapter(provider)
            return self._execute_with_retry(
                adapter,
                "tool_call",
                provider,
                messages,
                tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )

        except LLMErrorEnhanced as e:
            # Try Ollama fallback if enabled and error is retryable
            if self.config.enable_ollama_fallback and e.retryable:
                ollama = self.adapters.get("ollama")
                if ollama:
                    try:
                        return ollama.tool_call(
                            messages,
                            tools,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=timeout,
                        )
                    except Exception:
                        # Re-raise original error if fallback also fails
                        pass
            raise
