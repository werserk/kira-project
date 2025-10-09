"""LLM integration layer for LangGraph agent.

Bridges LangGraph with Kira's multi-provider LLM router.
Ensures LangGraph works with any LLM provider (OpenAI, Anthropic, OpenRouter, Ollama).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..adapters.llm import LLMAdapter, LLMRouter, Message

logger = logging.getLogger(__name__)

__all__ = ["create_langgraph_llm_adapter", "LangGraphLLMBridge"]


class LangGraphLLMBridge:
    """Bridge between LangGraph and LLMRouter.

    Wraps LLMRouter to provide LLMAdapter interface for LangGraph nodes.
    Ensures provider-agnostic operation with fallback support.
    """

    def __init__(self, llm_router: LLMRouter, task_type: str = "planning") -> None:
        """Initialize LLM bridge.

        Parameters
        ----------
        llm_router
            LLM router with multi-provider support
        task_type
            Task type for routing: "planning", "structuring", "default"
        """
        self.llm_router = llm_router
        self.task_type = task_type
        logger.info(f"Initialized LangGraph LLM bridge with task_type={task_type}")

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0,
    ) -> Any:
        """Generate text completion.

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

        Returns
        -------
        LLMResponse
            Generated response with fallback support
        """
        from ..adapters.llm import TaskType

        # Map string to TaskType enum
        task_type_map = {
            "planning": TaskType.PLANNING,
            "structuring": TaskType.STRUCTURING,
            "default": TaskType.DEFAULT,
        }
        task_type_enum = task_type_map.get(self.task_type, TaskType.DEFAULT)

        return self.llm_router.generate(
            prompt=prompt,
            task_type=task_type_enum,
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
    ) -> Any:
        """Multi-turn chat conversation.

        Parameters
        ----------
        messages
            Conversation messages
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
            Chat response with fallback support
        """
        from ..adapters.llm import TaskType

        task_type_map = {
            "planning": TaskType.PLANNING,
            "structuring": TaskType.STRUCTURING,
            "default": TaskType.DEFAULT,
        }
        task_type_enum = task_type_map.get(self.task_type, TaskType.DEFAULT)

        return self.llm_router.chat(
            messages=messages,
            task_type=task_type_enum,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def tool_call(
        self,
        messages: list[Message],
        tools: list[Any],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 60.0,
    ) -> Any:
        """Chat with tool calling support.

        Parameters
        ----------
        messages
            Conversation messages
        tools
            Available tools
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
            Response with tool calls and fallback support
        """
        from ..adapters.llm import TaskType

        task_type_enum = TaskType.STRUCTURING  # Tool calls are structuring tasks

        return self.llm_router.tool_call(
            messages=messages,
            tools=tools,
            task_type=task_type_enum,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )


def create_langgraph_llm_adapter(
    *,
    api_keys: dict[str, str] | None = None,
    planning_provider: str = "anthropic",
    structuring_provider: str = "openai",
    default_provider: str = "openrouter",
    enable_ollama_fallback: bool = True,
    task_type: str = "planning",
) -> LangGraphLLMBridge:
    """Factory to create LLM adapter for LangGraph with multi-provider support.

    Parameters
    ----------
    api_keys
        API keys for providers: {"openai": "...", "anthropic": "...", ...}
    planning_provider
        Provider for planning tasks (default: anthropic)
    structuring_provider
        Provider for JSON structuring (default: openai)
    default_provider
        Default provider (default: openrouter)
    enable_ollama_fallback
        Enable fallback to local Ollama on failures
    task_type
        Task type for LangGraph: "planning", "structuring", "default"

    Returns
    -------
    LangGraphLLMBridge
        LLM adapter that works with any provider

    Examples
    --------
    >>> # Use with LangGraphExecutor
    >>> llm = create_langgraph_llm_adapter(
    ...     api_keys={"anthropic": "sk-..."},
    ...     enable_ollama_fallback=True,
    ... )
    >>> executor = LangGraphExecutor(llm, tool_registry)
    >>> result = executor.execute("Create a task")

    >>> # Provider routing:
    >>> # - Planning tasks → Anthropic (Claude)
    >>> # - JSON structuring → OpenAI (GPT-4)
    >>> # - Fallback → Ollama (local)
    """
    from ..adapters.llm import LLMRouter, RouterConfig

    # Create router config
    router_config = RouterConfig(
        planning_provider=planning_provider,
        structuring_provider=structuring_provider,
        default_provider=default_provider,
        enable_ollama_fallback=enable_ollama_fallback,
    )

    # Initialize providers with API keys
    providers = {}
    if api_keys:
        if "openai" in api_keys:
            from ..adapters.llm import OpenAIAdapter

            providers["openai"] = OpenAIAdapter(api_key=api_keys["openai"])

        if "anthropic" in api_keys:
            from ..adapters.llm import AnthropicAdapter

            providers["anthropic"] = AnthropicAdapter(api_key=api_keys["anthropic"])

        if "openrouter" in api_keys:
            from ..adapters.llm import OpenRouterAdapter

            providers["openrouter"] = OpenRouterAdapter(api_key=api_keys["openrouter"])

    # Always add Ollama for fallback
    if enable_ollama_fallback:
        from ..adapters.llm import OllamaAdapter

        providers["ollama"] = OllamaAdapter()

    # Create router
    llm_router = LLMRouter(config=router_config, providers=providers)

    # Create bridge
    bridge = LangGraphLLMBridge(llm_router, task_type=task_type)

    logger.info(
        f"Created LangGraph LLM adapter: "
        f"providers={list(providers.keys())}, "
        f"fallback={enable_ollama_fallback}, "
        f"task_type={task_type}"
    )

    return bridge

