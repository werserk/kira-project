"""Agent configuration and settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentConfig:
    """Configuration for Kira agent."""

    # LLM provider settings - all providers
    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-3-5-sonnet-20241022"
    openai_api_key: str = ""
    openai_default_model: str = "gpt-4-turbo-preview"
    openrouter_api_key: str = ""
    openrouter_default_model: str = "anthropic/claude-3.5-sonnet"
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3"

    # Router configuration
    planning_provider: str = "anthropic"  # Best for planning
    structuring_provider: str = "openai"  # Best for JSON
    default_provider: str = "openrouter"  # Fallback
    enable_ollama_fallback: bool = True

    # Legacy field for backwards compatibility
    llm_provider: str = "openrouter"

    # RAG and Memory
    enable_rag: bool = False
    rag_index_path: str | None = None
    memory_max_exchanges: int = 3

    # Agent behavior
    max_tool_calls: int = 10
    max_tokens: int = 4000
    timeout: float = 60.0
    temperature: float = 0.7

    # Service settings
    host: str = "0.0.0.0"
    port: int = 8000

    # Telegram gateway (optional)
    telegram_bot_token: str = ""
    enable_telegram_webhook: bool = False

    # Vault settings
    vault_path: Path | None = None

    @classmethod
    def from_env(cls) -> AgentConfig:
        """Load configuration from environment variables.

        DEPRECATED: Use from_settings() instead.
        This method is kept for backward compatibility.
        """
        from ..config.settings import load_settings

        settings = load_settings()
        return cls.from_settings(settings)

    @classmethod
    def from_settings(cls, settings: Any) -> AgentConfig:
        """Create AgentConfig from Settings object.

        Parameters
        ----------
        settings
            Settings object from kira.config.settings

        Returns
        -------
        AgentConfig
            Configured agent config
        """
        return cls(
            # LLM providers
            anthropic_api_key=settings.anthropic_api_key,
            anthropic_default_model=settings.anthropic_default_model,
            openai_api_key=settings.openai_api_key,
            openai_default_model=settings.openai_default_model,
            openrouter_api_key=settings.openrouter_api_key,
            openrouter_default_model=settings.openrouter_default_model,
            ollama_base_url=settings.ollama_base_url,
            ollama_default_model=settings.ollama_default_model,
            # Router config
            planning_provider=settings.planning_provider,
            structuring_provider=settings.structuring_provider,
            default_provider=settings.default_provider,
            enable_ollama_fallback=settings.enable_ollama_fallback,
            # Legacy
            llm_provider=settings.llm_provider,
            # RAG and Memory
            enable_rag=settings.enable_rag,
            rag_index_path=settings.rag_index_path,
            memory_max_exchanges=settings.memory_max_exchanges,
            # Agent behavior
            max_tool_calls=settings.agent_max_tool_calls,
            max_tokens=settings.agent_max_tokens,
            timeout=settings.agent_timeout,
            temperature=settings.agent_temperature,
            # Service
            host=settings.agent_host,
            port=settings.agent_port,
            # Telegram
            telegram_bot_token=settings.telegram_bot_token or "",
            enable_telegram_webhook=settings.enable_telegram_webhook,
            # Vault
            vault_path=settings.vault_path,
        )
