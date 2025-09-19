"""
JSON Schema для валидации манифеста плагина kira-plugin.json
"""
import json
from typing import Any, Dict, List, Optional

from jsonschema import Draft7Validator, ValidationError, validate

# JSON Schema для валидации kira-plugin.json
PLUGIN_MANIFEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "name",
        "version",
        "displayName",
        "description",
        "publisher",
        "engines",
        "permissions",
        "entry",
        "capabilities",
        "contributes"
    ],
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
            "minLength": 3,
            "maxLength": 50,
            "description": "Уникальное имя плагина (kebab-case)"
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+(-[a-zA-Z0-9.-]+)?$",
            "description": "Версия плагина в формате semver"
        },
        "displayName": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
            "description": "Человекочитаемое название плагина"
        },
        "description": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500,
            "description": "Описание функциональности плагина"
        },
        "publisher": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$",
            "minLength": 2,
            "maxLength": 30,
            "description": "Имя издателя плагина"
        },
        "engines": {
            "type": "object",
            "required": ["kira"],
            "properties": {
                "kira": {
                    "type": "string",
                    "pattern": "^\\^?\\d+\\.\\d+\\.\\d+$",
                    "description": "Требуемая версия ядра Kira"
                }
            },
            "additionalProperties": False
        },
        "permissions": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "calendar.read",
                    "calendar.write",
                    "vault.read",
                    "vault.write",
                    "fs.read",
                    "fs.write",
                    "net",
                    "secrets.read",
                    "secrets.write",
                    "events.publish",
                    "events.subscribe",
                    "scheduler.create",
                    "scheduler.cancel",
                    "sandbox.execute"
                ]
            },
            "uniqueItems": True,
            "description": "Список разрешений, требуемых плагином"
        },
        "entry": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9_.]+:[a-zA-Z0-9_]+$",
            "description": "Точка входа в формате module:function"
        },
        "capabilities": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "pull",
                    "push",
                    "timebox",
                    "notify",
                    "schedule",
                    "transform",
                    "validate",
                    "sync",
                    "normalize"
                ]
            },
            "uniqueItems": True,
            "description": "Возможности, предоставляемые плагином"
        },
        "configSchema": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_.]+$": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["string", "integer", "number", "boolean", "array", "object"]
                        },
                        "default": {
                            "description": "Значение по умолчанию"
                        },
                        "description": {
                            "type": "string",
                            "maxLength": 200
                        },
                        "required": {
                            "type": "boolean"
                        },
                        "enum": {
                            "type": "array",
                            "minItems": 1
                        },
                        "minimum": {
                            "type": "number"
                        },
                        "maximum": {
                            "type": "number"
                        },
                        "minLength": {
                            "type": "integer",
                            "minimum": 0
                        },
                        "maxLength": {
                            "type": "integer",
                            "minimum": 1
                        }
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False,
            "description": "Схема конфигурации плагина"
        },
        "contributes": {
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9_.]+$"
                    },
                    "uniqueItems": True,
                    "description": "События, на которые подписывается плагин"
                },
                "commands": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9_.]+$"
                    },
                    "uniqueItems": True,
                    "description": "Команды, предоставляемые плагином"
                },
                "adapters": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["telegram", "gcal", "filesystem", "email", "webhook"]
                    },
                    "uniqueItems": True,
                    "description": "Адаптеры, с которыми работает плагин"
                }
            },
            "additionalProperties": False,
            "description": "Вклад плагина в систему"
        },
        "sandbox": {
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["subprocess", "thread", "inline"],
                    "default": "subprocess"
                },
                "timeoutMs": {
                    "type": "integer",
                    "minimum": 1000,
                    "maximum": 300000,
                    "default": 30000
                },
                "memoryLimit": {
                    "type": "integer",
                    "minimum": 64,
                    "maximum": 1024,
                    "description": "Лимит памяти в MB"
                },
                "networkAccess": {
                    "type": "boolean",
                    "default": False
                },
                "fsAccess": {
                    "type": "object",
                    "properties": {
                        "read": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "write": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False,
            "description": "Настройки изоляции плагина"
        },
        "dependencies": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_.-]+$": {
                    "type": "string",
                    "pattern": "^[~^]?\\d+\\.\\d+\\.\\d+$"
                }
            },
            "description": "Зависимости плагина"
        },
        "keywords": {
            "type": "array",
            "items": {
                "type": "string",
                "maxLength": 30
            },
            "maxItems": 10,
            "uniqueItems": True,
            "description": "Ключевые слова для поиска"
        },
        "homepage": {
            "type": "string",
            "format": "uri",
            "description": "URL домашней страницы плагина"
        },
        "repository": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["git", "hg", "svn"]
                },
                "url": {
                    "type": "string",
                    "format": "uri"
                }
            },
            "required": ["type", "url"],
            "additionalProperties": False
        },
        "bugs": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri"
                },
                "email": {
                    "type": "string",
                    "format": "email"
                }
            },
            "additionalProperties": False
        },
        "license": {
            "type": "string",
            "enum": [
                "MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause",
                "ISC", "Unlicense", "Proprietary"
            ]
        }
    },
    "additionalProperties": False
}


class PluginManifestValidator:
    """Валидатор манифеста плагина"""

    def __init__(self):
        self.validator = Draft7Validator(PLUGIN_MANIFEST_SCHEMA)

    def validate_manifest(self, manifest_data: Dict[str, Any]) -> List[str]:
        """
        Валидирует манифест плагина

        Args:
            manifest_data: Словарь с данными манифеста

        Returns:
            Список ошибок валидации (пустой если валидно)
        """
        collected: List[str] = []

        try:
            for error in sorted(
                self.validator.iter_errors(manifest_data),
                key=lambda err: list(err.absolute_path),
            ):
                location = " -> ".join(str(part) for part in error.absolute_path) or "<root>"
                collected.append(
                    f"[{error.validator}] {error.message} (path: {location})"
                )
        except Exception as exc:
            collected.append(f"Неожиданная ошибка: {exc}")

        return collected

    def validate_manifest_file(self, file_path: str) -> List[str]:
        """
        Валидирует манифест из файла

        Args:
            file_path: Путь к файлу kira-plugin.json

        Returns:
            Список ошибок валидации (пустой если валидно)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            return self.validate_manifest(manifest_data)
        except FileNotFoundError:
            return [f"Файл не найден: {file_path}"]
        except json.JSONDecodeError as e:
            return [f"Ошибка JSON: {str(e)}"]
        except Exception as e:
            return [f"Ошибка чтения файла: {str(e)}"]


def validate_plugin_manifest(manifest_data: Dict[str, Any]) -> bool:
    """
    Быстрая проверка валидности манифеста

    Args:
        manifest_data: Словарь с данными манифеста

    Returns:
        True если манифест валиден, False иначе
    """
    validator = PluginManifestValidator()
    errors = validator.validate_manifest(manifest_data)
    return len(errors) == 0


def get_manifest_schema() -> Dict[str, Any]:
    """
    Возвращает JSON Schema для манифеста плагина

    Returns:
        Словарь с JSON Schema
    """
    return PLUGIN_MANIFEST_SCHEMA.copy()


# Пример использования
if __name__ == "__main__":
    # Пример валидного манифеста
    example_manifest = {
        "name": "kira-calendar",
        "version": "0.4.2",
        "displayName": "Calendar Sync",
        "description": "Sync events & timeboxing",
        "publisher": "werserk",
        "engines": {"kira": "^1.0.0"},
        "permissions": ["calendar.write", "net", "secrets.read"],
        "entry": "kira_plugin_calendar.plugin:activate",
        "capabilities": ["pull", "push", "timebox"],
        "configSchema": {
            "calendar.default": {"type": "string"},
            "timebox.length": {"type": "integer", "default": 90}
        },
        "contributes": {
            "events": ["event.created", "task.due_soon"],
            "commands": ["calendar.pull", "calendar.push"]
        },
        "sandbox": {"strategy": "subprocess", "timeoutMs": 60000}
    }

    validator = PluginManifestValidator()
    errors = validator.validate_manifest(example_manifest)

    if errors:
        print("Ошибки валидации:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Манифест валиден!")
