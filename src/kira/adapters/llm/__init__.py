"""LLM Adapter module for Kira agent system.

Provides provider-agnostic interface for LLM interactions with support for:
- Text generation
- Chat conversations
- Tool calling
- Multiple providers (OpenRouter, OpenAI, Anthropic, Ollama)
- Multi-provider routing with fallback
"""

from .adapter import LLMAdapter, LLMError, LLMRateLimitError, LLMResponse, LLMTimeoutError, Message, Tool, ToolCall
from .anthropic_adapter import AnthropicAdapter
from .ollama_adapter import OllamaAdapter
from .openai_adapter import OpenAIAdapter
from .openrouter_adapter import OpenRouterAdapter
from .router import LLMErrorEnhanced, LLMRouter, RouterConfig, TaskType

__all__ = [
    "LLMAdapter",
    "LLMResponse",
    "Message",
    "Tool",
    "ToolCall",
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMErrorEnhanced",
    "OpenAIAdapter",
    "OpenRouterAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
    "LLMRouter",
    "RouterConfig",
    "TaskType",
]
