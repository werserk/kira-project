"""
Конфигурация Kira
"""

from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """
    Загружает конфигурацию из файла

    Args:
        config_path: Путь к файлу конфигурации (по умолчанию: kira.yaml)

    Returns:
        Словарь с конфигурацией
    """
    if config_path is None:
        config_path = "kira.yaml"

    config_file = Path(config_path)

    if not config_file.exists():
        # Возвращаем конфигурацию по умолчанию
        return {
            "vault": {"path": "/tmp/kira-vault", "tz": "UTC"},
            "adapters": {"telegram": {"enabled": False}, "gcal": {"enabled": False}},
            "policies": {"mode": "Focus", "confirm_external_writes": True},
            "security": {"secrets_from_env": True, "allow_fs_exec": False},
        }

    try:
        with open(config_file, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}")
        return {}


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
