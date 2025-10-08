"""Centralized configuration and secrets management (Phase 5, Point 18).

Loads configuration from .env file and provides typed access to settings.

DoD:
- Fresh checkout boots with a single .env
- Missing config produces clear errors
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "Settings",
    "load_settings",
    "get_settings",
    "ConfigError",
]


class ConfigError(Exception):
    """Raised when configuration is missing or invalid (Phase 5, Point 18 DoD)."""

    pass


@dataclass
class Settings:
    """Centralized settings for Kira (Phase 0 + Phase 5, Point 18).

    All configuration in one place:
    - Mode (alpha/beta/stable)
    - Vault path
    - Default timezone
    - Feature flags (GCal, Telegram, Plugins)
    - GCal sync parameters
    - Sandbox limits
    - Logging config

    Attributes
    ----------
    mode : str
        Runtime mode: alpha, beta, or stable (Phase 0, Point 1)
    vault_path : Path
        Path to vault directory (required)
    default_timezone : str
        Default timezone (default: UTC)
    gcal_enabled : bool
        Enable Google Calendar sync (Phase 0, Point 1: default false)
    telegram_enabled : bool
        Enable Telegram adapter (Phase 0, Point 1: default false)
    enable_plugins : bool
        Enable plugin system (Phase 0, Point 1: default false)
    gcal_calendar_id : str | None
        GCal calendar ID
    gcal_sync_interval_minutes : int
        Sync interval in minutes
    sandbox_max_cpu_seconds : float
        Plugin CPU time limit
    sandbox_max_memory_mb : int
        Plugin memory limit
    sandbox_allow_network : bool
        Allow plugin network access
    log_level : str
        Logging level
    log_file : Path | None
        Log file path
    """

    # Core settings (required fields first)
    vault_path: Path

    # Phase 0, Point 1: Runtime mode
    mode: str = "alpha"
    default_timezone: str = "UTC"

    # Phase 0, Point 1: Feature flags (integrations off by default)
    gcal_enabled: bool = False
    telegram_enabled: bool = False
    enable_plugins: bool = False

    # Google Calendar sync
    gcal_calendar_id: str | None = None
    gcal_sync_interval_minutes: int = 15
    gcal_credentials_file: str | None = None

    # Plugin sandbox limits
    sandbox_max_cpu_seconds: float = 30.0
    sandbox_max_memory_mb: int = 256
    sandbox_allow_network: bool = False

    # Logging
    log_level: str = "INFO"
    log_file: Path | None = None

    # Telegram (optional)
    telegram_bot_token: str | None = None
    telegram_allowed_users: list[int] = field(default_factory=list)

    def __post_init__(self):
        """Validate settings after initialization."""
        # Ensure vault_path is Path
        if isinstance(self.vault_path, str):
            self.vault_path = Path(self.vault_path)

        # Ensure log_file is Path (if set)
        if self.log_file and isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)

        # Validate required fields
        if not self.vault_path:
            raise ConfigError("vault_path is required")

    @classmethod
    def from_env(cls, env_file: Path | str | None = None) -> Settings:
        """Load settings from environment (Phase 5, Point 18).

        Loads from .env file if present, otherwise from os.environ.

        Parameters
        ----------
        env_file
            Path to .env file (default: .env in current directory)

        Returns
        -------
        Settings
            Loaded settings

        Raises
        ------
        ConfigError
            If required settings are missing or invalid
        """
        # Load .env file if exists
        if env_file is None:
            env_file = Path(".env")

        if isinstance(env_file, str):
            env_file = Path(env_file)

        if env_file.exists():
            load_env_file(env_file)

        # Load settings from environment
        try:
            vault_path = os.environ.get("KIRA_VAULT_PATH")
            if not vault_path:
                raise ConfigError("KIRA_VAULT_PATH is required. " "Set it in .env or environment.")

            # Parse settings
            settings = cls(
                # Phase 0, Point 1: Runtime mode (defaults to alpha)
                mode=os.environ.get("KIRA_MODE", "alpha"),
                vault_path=Path(vault_path),
                default_timezone=os.environ.get("KIRA_DEFAULT_TZ", "UTC"),
                # Phase 0, Point 1: Feature flags (off by default)
                gcal_enabled=os.environ.get("KIRA_GCAL_ENABLED", "false").lower() == "true",
                telegram_enabled=os.environ.get("KIRA_TELEGRAM_ENABLED", "false").lower() == "true",
                enable_plugins=os.environ.get("KIRA_ENABLE_PLUGINS", "false").lower() == "true",
                # GCal
                gcal_calendar_id=os.environ.get("KIRA_GCAL_CALENDAR_ID"),
                gcal_sync_interval_minutes=int(os.environ.get("KIRA_GCAL_SYNC_INTERVAL", "15")),
                gcal_credentials_file=os.environ.get("KIRA_GCAL_CREDENTIALS_FILE"),
                # Sandbox
                sandbox_max_cpu_seconds=float(os.environ.get("KIRA_SANDBOX_MAX_CPU", "30.0")),
                sandbox_max_memory_mb=int(os.environ.get("KIRA_SANDBOX_MAX_MEMORY", "256")),
                sandbox_allow_network=os.environ.get("KIRA_SANDBOX_ALLOW_NETWORK", "false").lower() == "true",
                # Logging
                log_level=os.environ.get("KIRA_LOG_LEVEL", "INFO"),
                log_file=Path(os.environ["KIRA_LOG_FILE"]) if "KIRA_LOG_FILE" in os.environ else None,
                # Telegram
                telegram_bot_token=os.environ.get("KIRA_TELEGRAM_BOT_TOKEN"),
                telegram_allowed_users=parse_int_list(os.environ.get("KIRA_TELEGRAM_ALLOWED_USERS", "")),
            )

            return settings

        except (ValueError, KeyError) as exc:
            raise ConfigError(f"Invalid configuration: {exc}") from exc


def load_env_file(env_file: Path) -> None:
    """Load environment variables from .env file.

    Parameters
    ----------
    env_file
        Path to .env file
    """
    with open(env_file) as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                os.environ[key] = value


def parse_int_list(value: str) -> list[int]:
    """Parse comma-separated list of integers.

    Parameters
    ----------
    value
        Comma-separated integers

    Returns
    -------
    list[int]
        Parsed integers
    """
    if not value:
        return []

    try:
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError:
        return []


# Global settings instance
_settings: Settings | None = None


def load_settings(env_file: Path | str | None = None) -> Settings:
    """Load settings from environment (Phase 5, Point 18).

    DoD: Fresh checkout boots with a single .env

    Parameters
    ----------
    env_file
        Path to .env file

    Returns
    -------
    Settings
        Loaded settings

    Raises
    ------
    ConfigError
        If required settings missing (clear error message)
    """
    global _settings
    _settings = Settings.from_env(env_file)
    return _settings


def get_settings() -> Settings:
    """Get current settings (Phase 5, Point 18).

    DoD: Missing config produces clear errors

    Returns
    -------
    Settings
        Current settings

    Raises
    ------
    ConfigError
        If settings not loaded
    """
    global _settings
    if _settings is None:
        raise ConfigError("Settings not loaded. Call load_settings() first or set KIRA_VAULT_PATH.")
    return _settings


def generate_example_env(output_path: Path | None = None) -> str:
    """Generate example .env file with all settings (Phase 0, Point 1).

    Parameters
    ----------
    output_path
        Optional path to write .env file

    Returns
    -------
    str
        Example .env contents
    """
    example = """# Kira Configuration (Phase 0 + Phase 5)
# Copy this to .env and adjust values
# DoD: Kira bootstraps with a single .env; integrations are off by default

# ====================
# Phase 0: Runtime Mode & Feature Flags
# ====================

# Runtime mode (optional, default: alpha)
# Options: alpha, beta, stable
KIRA_MODE=alpha

# ====================
# Core Settings
# ====================

# Path to vault directory (required)
KIRA_VAULT_PATH=vault

# Default timezone (optional, default: UTC)
# Examples: UTC, America/New_York, Europe/Brussels
KIRA_DEFAULT_TZ=Europe/Brussels

# ====================
# Phase 0: Feature Flags (ALL OFF BY DEFAULT)
# ====================

# Enable Google Calendar sync (optional, default: false)
KIRA_GCAL_ENABLED=false

# Enable Telegram adapter (optional, default: false)
KIRA_TELEGRAM_ENABLED=false

# Enable plugin system (optional, default: false)
KIRA_ENABLE_PLUGINS=false

# ====================
# Google Calendar Sync (requires KIRA_ENABLE_GCAL=true)
# ====================

# GCal calendar ID (required if GCAL_ENABLED=true)
# KIRA_GCAL_CALENDAR_ID=your-calendar-id@group.calendar.google.com

# Sync interval in minutes (optional, default: 15)
KIRA_GCAL_SYNC_INTERVAL=15

# Path to GCal credentials JSON (required if GCAL_ENABLED=true)
# KIRA_GCAL_CREDENTIALS_FILE=/home/user/.kira/gcal-credentials.json

# ====================
# Plugin Sandbox (requires KIRA_ENABLE_PLUGINS=true)
# ====================

# Max CPU time for plugins in seconds (optional, default: 30)
KIRA_SANDBOX_MAX_CPU=30.0

# Max memory for plugins in MB (optional, default: 256)
KIRA_SANDBOX_MAX_MEMORY=256

# Allow plugin network access (optional, default: false)
KIRA_SANDBOX_ALLOW_NETWORK=false

# ====================
# Logging
# ====================

# Log level (optional, default: INFO)
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
KIRA_LOG_LEVEL=INFO

# Log file path (optional, logs to console if not set)
# KIRA_LOG_FILE=logs/kira.log

# ====================
# Telegram Integration (requires KIRA_ENABLE_TELEGRAM=true)
# ====================

# Telegram bot token (required if TELEGRAM_ENABLED=true)
# KIRA_TELEGRAM_BOT_TOKEN=your-bot-token

# Comma-separated list of allowed user IDs (optional)
# KIRA_TELEGRAM_ALLOWED_USERS=123456789,987654321
"""

    if output_path:
        output_path.write_text(example)

    return example
