"""Centralized configuration management for Kira.

Supports:
- Default configuration from config/defaults.yaml
- User overrides from kira.yaml
- Environment variable overrides (KIRA_*)
- Nested key access with dot notation
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

__all__ = ["Config", "load_config", "get_config", "save_config"]

# Global config instance
_config_instance: Config | None = None


class Config:
    """Centralized configuration with defaults, overrides, and env vars.

    Configuration priority (highest to lowest):
    1. Environment variables (KIRA_*)
    2. User config (kira.yaml)
    3. Defaults (config/defaults.yaml)

    Example:
        >>> config = Config.load()
        >>> timeout = config.get("sandbox.timeout_ms", 30000)
        >>> vault_path = config.get("vault.path", "vault")
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        """Initialize configuration.

        Parameters
        ----------
        data
            Configuration data dictionary
        """
        self._data = data or {}

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
        defaults_path: str | Path | None = None,
    ) -> Config:
        """Load configuration from files and environment.

        Parameters
        ----------
        config_path
            Path to user config file (default: kira.yaml)
        defaults_path
            Path to defaults config (default: config/defaults.yaml)

        Returns
        -------
        Config
            Loaded configuration instance
        """
        # Load defaults
        if defaults_path is None:
            # Try to find defaults relative to this file
            module_dir = Path(__file__).parent.parent.parent.parent
            defaults_path = module_dir / "config" / "defaults.yaml"

        defaults = cls._load_yaml_file(defaults_path) if Path(defaults_path).exists() else {}

        # Load user config
        if config_path is None:
            config_path = Path("kira.yaml")

        user_config = cls._load_yaml_file(config_path) if Path(config_path).exists() else {}

        # Merge configurations (user overrides defaults)
        merged = cls._deep_merge(defaults, user_config)

        # Apply environment variable overrides
        merged = cls._apply_env_overrides(merged)

        return cls(merged)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Supports dot notation for nested keys:
        - "vault.path" → config["vault"]["path"]
        - "sandbox.timeout_ms" → config["sandbox"]["timeout_ms"]

        Parameters
        ----------
        key
            Configuration key (supports dot notation)
        default
            Default value if key not found

        Returns
        -------
        Any
            Configuration value or default
        """
        parts = key.split(".")
        value = self._data

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by key.

        Parameters
        ----------
        key
            Configuration key (supports dot notation)
        value
            Value to set
        """
        parts = key.split(".")
        data = self._data

        for part in parts[:-1]:
            if part not in data:
                data[part] = {}
            data = data[part]

        data[parts[-1]] = value

    def to_dict(self) -> dict[str, Any]:
        """Get full configuration as dictionary.

        Returns
        -------
        dict
            Configuration data
        """
        return self._data.copy()

    @staticmethod
    def _load_yaml_file(path: str | Path) -> dict[str, Any]:
        """Load YAML file.

        Parameters
        ----------
        path
            Path to YAML file

        Returns
        -------
        dict
            Loaded data
        """
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            return {}

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries.

        Parameters
        ----------
        base
            Base dictionary
        override
            Override dictionary

        Returns
        -------
        dict
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    @staticmethod
    def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides.

        Environment variables in format KIRA_SECTION_KEY override config values.
        Example: KIRA_VAULT_PATH overrides config["vault"]["path"]

        Parameters
        ----------
        config
            Base configuration

        Returns
        -------
        dict
            Configuration with env overrides applied
        """
        result = config.copy()

        # Common env var mappings
        env_mappings = {
            "KIRA_VAULT_PATH": "vault.path",
            "KIRA_LOG_LEVEL": "logging.level",
            "KIRA_LOG_PATH": "logging.path",
            "KIRA_TIMEZONE": "core.timezone",
            "KIRA_SANDBOX_TIMEOUT": "sandbox.timeout_ms",
            "KIRA_CONFIG": "config_path",
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Convert to appropriate type
                if config_key.endswith("_ms") or config_key.endswith("timeout"):
                    try:
                        value = int(value)
                    except ValueError:
                        pass

                # Set nested key
                parts = config_key.split(".")
                data = result
                for part in parts[:-1]:
                    if part not in data:
                        data[part] = {}
                    data = data[part]
                data[parts[-1]] = value

        return result


def get_config() -> Config:
    """Get global configuration instance (singleton).

    Returns
    -------
    Config
        Global configuration instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = Config.load()

    return _config_instance


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load configuration and return as dictionary (legacy compatibility).

    Args:
        config_path: Path to config file (default: kira.yaml)

    Returns:
        Configuration dictionary
    """
    config = Config.load(config_path=config_path)
    return config.to_dict()


def save_config(config: dict[str, Any], config_path: str | None = None) -> bool:
    """
    Сохраняет конфигурацию в файл

    Args:
        config: Словарь с конфигурацией
        config_path: Путь к файлу конфигурации (по умолчанию: kira.yaml)

    Returns:
        True если сохранение успешно, False иначе
    """
    if config_path is None:
        config_path = "kira.yaml"

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")
        return False
