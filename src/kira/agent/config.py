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
        """Load configuration from environment variables."""
        vault_path_str = os.getenv("KIRA_VAULT_PATH", "vault")
        vault_path = Path(vault_path_str) if vault_path_str else None

        return cls(
            # LLM providers
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_default_model=os.getenv("ANTHROPIC_DEFAULT_MODEL", "claude-3-5-sonnet-20241022"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_default_model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4-turbo-preview"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_default_model=os.getenv("OPENROUTER_DEFAULT_MODEL", "anthropic/claude-3.5-sonnet"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_default_model=os.getenv("OLLAMA_DEFAULT_MODEL", "llama3"),
            # Router config
            planning_provider=os.getenv("LLM_PLANNING_PROVIDER", "anthropic"),
            structuring_provider=os.getenv("LLM_STRUCTURING_PROVIDER", "openai"),
            default_provider=os.getenv("LLM_DEFAULT_PROVIDER", "openrouter"),
            enable_ollama_fallback=os.getenv("ENABLE_OLLAMA_FALLBACK", "true").lower() == "true",
            # Legacy
            llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
            # RAG and Memory
            enable_rag=os.getenv("ENABLE_RAG", "false").lower() == "true",
            rag_index_path=os.getenv("RAG_INDEX_PATH"),
            memory_max_exchanges=int(os.getenv("MEMORY_MAX_EXCHANGES", "3")),
            # Agent behavior
            max_tool_calls=int(os.getenv("KIRA_AGENT_MAX_TOOL_CALLS", "10")),
            max_tokens=int(os.getenv("KIRA_AGENT_MAX_TOKENS", "4000")),
            timeout=float(os.getenv("KIRA_AGENT_TIMEOUT", "60.0")),
            temperature=float(os.getenv("KIRA_AGENT_TEMPERATURE", "0.7")),
            # Service
            host=os.getenv("KIRA_AGENT_HOST", "0.0.0.0"),
            port=int(os.getenv("KIRA_AGENT_PORT", "8000")),
            # Telegram
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            enable_telegram_webhook=os.getenv("ENABLE_TELEGRAM_WEBHOOK", "false").lower() == "true",
            # Vault
            vault_path=vault_path,
        )
