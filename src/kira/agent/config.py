"""Agent configuration and settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentConfig:
    """Configuration for Kira agent."""

    # LLM provider settings
    llm_provider: str = "openrouter"
    openrouter_api_key: str = ""
    openrouter_default_model: str = "anthropic/claude-3.5-sonnet"
    openai_api_key: str = ""
    openai_default_model: str = "gpt-4-turbo-preview"

    # Agent behavior
    max_tool_calls: int = 10
    max_tokens: int = 4000
    timeout: float = 60.0
    temperature: float = 0.7

    # Service settings
    host: str = "0.0.0.0"
    port: int = 8000

    # Vault settings
    vault_path: Path | None = None

    @classmethod
    def from_env(cls) -> AgentConfig:
        """Load configuration from environment variables."""
        vault_path_str = os.getenv("KIRA_VAULT_PATH", "vault")
        vault_path = Path(vault_path_str) if vault_path_str else None

        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_default_model=os.getenv("OPENROUTER_DEFAULT_MODEL", "anthropic/claude-3.5-sonnet"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_default_model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4-turbo-preview"),
            max_tool_calls=int(os.getenv("KIRA_AGENT_MAX_TOOL_CALLS", "10")),
            max_tokens=int(os.getenv("KIRA_AGENT_MAX_TOKENS", "4000")),
            timeout=float(os.getenv("KIRA_AGENT_TIMEOUT", "60.0")),
            temperature=float(os.getenv("KIRA_AGENT_TEMPERATURE", "0.7")),
            host=os.getenv("KIRA_AGENT_HOST", "0.0.0.0"),
            port=int(os.getenv("KIRA_AGENT_PORT", "8000")),
            vault_path=vault_path,
        )
