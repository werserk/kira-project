"""LLM Adapter module for Kira agent system.

Provides provider-agnostic interface for LLM interactions with support for:
- Text generation
- Chat conversations
- Tool calling
- Multiple providers (OpenRouter, OpenAI)
"""

from .adapter import LLMAdapter, LLMError, LLMRateLimitError, LLMResponse, LLMTimeoutError, Message, Tool, ToolCall
from .openai_adapter import OpenAIAdapter
from .openrouter_adapter import OpenRouterAdapter

__all__ = [
    "LLMAdapter",
    "LLMResponse",
    "Message",
    "Tool",
    "ToolCall",
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "OpenAIAdapter",
    "OpenRouterAdapter",
]
