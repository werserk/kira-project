"""
Тесты для валидации манифеста плагина
"""
import json
import sys
from pathlib import Path

import pytest

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.plugin_sdk.manifest import (
    PluginManifestValidator,
    get_manifest_schema,
    validate_plugin_manifest,
)


class TestPluginManifestValidation:
    """Тесты валидации манифеста плагина"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.validator = PluginManifestValidator()

    def test_valid_manifest(self):
        """Тест валидного манифеста"""
        valid_manifest = {
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

        errors = self.validator.validate_manifest(valid_manifest)
        assert len(errors) == 0

    def test_missing_required_fields(self):
        """Тест отсутствующих обязательных полей"""
        incomplete_manifest = {
            "name": "test-plugin",
            "version": "1.0.0"
            # Отсутствуют обязательные поля
        }

        errors = self.validator.validate_manifest(incomplete_manifest)
        assert len(errors) > 0
        assert any("required" in error.lower() for error in errors)

    def test_invalid_name_format(self):
        """Тест неверного формата имени"""
        invalid_manifest = {
            "name": "Invalid-Name-With-Caps",  # Неверный формат
            "version": "1.0.0",
            "displayName": "Test Plugin",
            "description": "Test description",
            "publisher": "test",
            "engines": {"kira": "^1.0.0"},
            "permissions": ["vault.read"],
            "entry": "test.plugin:activate",
            "capabilities": ["pull"],
            "contributes": {"events": [], "commands": []}
        }

        errors = self.validator.validate_manifest(invalid_manifest)
        assert len(errors) > 0
        assert any("pattern" in error.lower() for error in errors)

    def test_invalid_permissions(self):
        """Тест неверных разрешений"""
        invalid_manifest = {
            "name": "test-plugin",
            "version": "1.0.0",
            "displayName": "Test Plugin",
            "description": "Test description",
            "publisher": "test",
            "engines": {"kira": "^1.0.0"},
            "permissions": ["invalid.permission", "another.invalid"],  # Неверные разрешения
            "entry": "test.plugin:activate",
            "capabilities": ["pull"],
            "contributes": {"events": [], "commands": []}
        }

        errors = self.validator.validate_manifest(invalid_manifest)
        assert len(errors) > 0
        assert any("enum" in error.lower() for error in errors)

    def test_invalid_version_format(self):
        """Тест неверного формата версии"""
        invalid_manifest = {
            "name": "test-plugin",
            "version": "not-a-version",  # Неверный формат
            "displayName": "Test Plugin",
            "description": "Test description",
            "publisher": "test",
            "engines": {"kira": "^1.0.0"},
            "permissions": ["vault.read"],
            "entry": "test.plugin:activate",
            "capabilities": ["pull"],
            "contributes": {"events": [], "commands": []}
        }

        errors = self.validator.validate_manifest(invalid_manifest)
        assert len(errors) > 0
        assert any("pattern" in error.lower() for error in errors)

    def test_invalid_entry_format(self):
        """Тест неверного формата точки входа"""
        invalid_manifest = {
            "name": "test-plugin",
            "version": "1.0.0",
            "displayName": "Test Plugin",
            "description": "Test description",
            "publisher": "test",
            "engines": {"kira": "^1.0.0"},
            "permissions": ["vault.read"],
            "entry": "invalid-entry-format",  # Неверный формат
            "capabilities": ["pull"],
            "contributes": {"events": [], "commands": []}
        }

        errors = self.validator.validate_manifest(invalid_manifest)
        assert len(errors) > 0
        assert any("pattern" in error.lower() for error in errors)

    def test_config_schema_validation(self):
        """Тест валидации схемы конфигурации"""
        manifest_with_config = {
            "name": "test-plugin",
            "version": "1.0.0",
            "displayName": "Test Plugin",
            "description": "Test description",
            "publisher": "test",
            "engines": {"kira": "^1.0.0"},
            "permissions": ["vault.read"],
            "entry": "test.plugin:activate",
            "capabilities": ["pull"],
            "contributes": {"events": [], "commands": []},
            "configSchema": {
                "test.string": {
                    "type": "string",
                    "default": "default_value",
                    "description": "Test string config"
                },
                "test.number": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "default": 50
                },
                "test.boolean": {
                    "type": "boolean",
                    "default": False
                }
            }
        }

        errors = self.validator.validate_manifest(manifest_with_config)
        assert len(errors) == 0

    def test_sandbox_configuration(self):
        """Тест конфигурации песочницы"""
        manifest_with_sandbox = {
            "name": "test-plugin",
            "version": "1.0.0",
            "displayName": "Test Plugin",
            "description": "Test description",
            "publisher": "test",
            "engines": {"kira": "^1.0.0"},
            "permissions": ["vault.read"],
            "entry": "test.plugin:activate",
            "capabilities": ["pull"],
            "contributes": {"events": [], "commands": []},
            "sandbox": {
                "strategy": "subprocess",
                "timeoutMs": 30000,
                "memoryLimit": 128,
                "networkAccess": True,
                "fsAccess": {
                    "read": ["/tmp"],
                    "write": ["/tmp/plugin"]
                }
            }
        }

        errors = self.validator.validate_manifest(manifest_with_sandbox)
        assert len(errors) == 0

    def test_validate_plugin_manifest_function(self):
        """Тест функции быстрой валидации"""
        valid_manifest = {
            "name": "test-plugin",
            "version": "1.0.0",
            "displayName": "Test Plugin",
            "description": "Test description",
            "publisher": "test",
            "engines": {"kira": "^1.0.0"},
            "permissions": ["vault.read"],
            "entry": "test.plugin:activate",
            "capabilities": ["pull"],
            "contributes": {"events": [], "commands": []}
        }

        assert validate_plugin_manifest(valid_manifest) == True

        invalid_manifest = {
            "name": "test-plugin"
            # Отсутствуют обязательные поля
        }

        assert validate_plugin_manifest(invalid_manifest) == False

    def test_get_manifest_schema(self):
        """Тест получения схемы манифеста"""
        schema = get_manifest_schema()

        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Проверяем наличие ключевых свойств
        required_fields = schema["required"]
        assert "name" in required_fields
        assert "version" in required_fields
        assert "entry" in required_fields
        assert "permissions" in required_fields


class TestManifestFileValidation:
    """Тесты валидации файлов манифеста"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.validator = PluginManifestValidator()
        self.test_dir = Path(__file__).parent / "test_manifests"
        self.test_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """Очистка после каждого теста"""
        # Удаляем тестовые файлы
        if self.test_dir.exists():
            for file in self.test_dir.glob("*.json"):
                file.unlink()
            self.test_dir.rmdir()

    def test_validate_valid_manifest_file(self):
        """Тест валидации валидного файла манифеста"""
        valid_manifest = {
            "name": "test-plugin",
            "version": "1.0.0",
            "displayName": "Test Plugin",
            "description": "Test description",
            "publisher": "test",
            "engines": {"kira": "^1.0.0"},
            "permissions": ["vault.read"],
            "entry": "test.plugin:activate",
            "capabilities": ["pull"],
            "contributes": {"events": [], "commands": []}
        }

        manifest_file = self.test_dir / "valid-plugin.json"
        with open(manifest_file, 'w') as f:
            json.dump(valid_manifest, f)

        errors = self.validator.validate_manifest_file(str(manifest_file))
        assert len(errors) == 0

    def test_validate_invalid_json_file(self):
        """Тест валидации файла с неверным JSON"""
        invalid_json_file = self.test_dir / "invalid.json"
        with open(invalid_json_file, 'w') as f:
            f.write("{ invalid json }")

        errors = self.validator.validate_manifest_file(str(invalid_json_file))
        assert len(errors) > 0
        assert any("JSON" in error for error in errors)

    def test_validate_nonexistent_file(self):
        """Тест валидации несуществующего файла"""
        nonexistent_file = self.test_dir / "nonexistent.json"

        errors = self.validator.validate_manifest_file(str(nonexistent_file))
        assert len(errors) > 0
        assert any("не найден" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__])
