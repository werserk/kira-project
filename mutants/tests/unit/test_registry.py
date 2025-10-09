"""
Тесты для реестров плагинов и адаптеров
"""

import sys
import tempfile
from pathlib import Path

import yaml

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.registry import AdapterRegistry, PluginRegistry


class TestPluginRegistry:
    """Тесты реестра плагинов"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.temp_dir = tempfile.mkdtemp()
        self.registry_file = Path(self.temp_dir) / "plugins_test.yaml"

        # Создаем тестовый реестр
        test_plugins = {
            "plugins": [
                {
                    "name": "kira-inbox",
                    "path": "src/kira/plugins/inbox",
                    "enabled": True,
                },
                {
                    "name": "kira-calendar",
                    "path": "src/kira/plugins/calendar",
                    "enabled": False,
                },
                {
                    "name": "kira-deadlines",
                    "path": "src/kira/plugins/deadlines",
                    "enabled": True,
                },
            ]
        }

        with open(self.registry_file, "w", encoding="utf-8") as f:
            yaml.dump(test_plugins, f)

        self.registry = PluginRegistry(str(self.registry_file))

    def teardown_method(self):
        """Очистка после каждого теста"""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_registry(self):
        """Тест загрузки реестра"""
        plugins = self.registry.get_plugins()
        assert len(plugins) == 3
        assert plugins[0]["name"] == "kira-inbox"
        assert plugins[1]["name"] == "kira-calendar"
        assert plugins[2]["name"] == "kira-deadlines"

    def test_get_enabled_plugins(self):
        """Тест получения включенных плагинов"""
        enabled_plugins = self.registry.get_enabled_plugins()
        assert len(enabled_plugins) == 2
        enabled_names = [p["name"] for p in enabled_plugins]
        assert "kira-inbox" in enabled_names
        assert "kira-deadlines" in enabled_names
        assert "kira-calendar" not in enabled_names

    def test_get_plugin(self):
        """Тест получения плагина по имени"""
        plugin = self.registry.get_plugin("kira-inbox")
        assert plugin is not None
        assert plugin["name"] == "kira-inbox"
        assert plugin["path"] == "src/kira/plugins/inbox"
        assert plugin["enabled"]

        # Несуществующий плагин
        plugin = self.registry.get_plugin("nonexistent")
        assert plugin is None

    def test_is_plugin_enabled(self):
        """Тест проверки включенности плагина"""
        assert self.registry.is_plugin_enabled("kira-inbox")
        assert not self.registry.is_plugin_enabled("kira-calendar")
        assert self.registry.is_plugin_enabled("kira-deadlines")
        assert not self.registry.is_plugin_enabled("nonexistent")

    def test_get_plugin_path(self):
        """Тест получения пути к плагину"""
        path = self.registry.get_plugin_path("kira-inbox")
        assert path is not None
        assert str(path) == "src/kira/plugins/inbox"

        # Несуществующий плагин
        path = self.registry.get_plugin_path("nonexistent")
        assert path is None

    def test_empty_registry(self):
        """Тест пустого реестра"""
        empty_file = Path(self.temp_dir) / "empty.yaml"
        empty_file.touch()

        empty_registry = PluginRegistry(str(empty_file))
        assert len(empty_registry.get_plugins()) == 0
        assert len(empty_registry.get_enabled_plugins()) == 0

    def test_nonexistent_registry_file(self):
        """Тест несуществующего файла реестра"""
        nonexistent_file = Path(self.temp_dir) / "nonexistent.yaml"
        registry = PluginRegistry(str(nonexistent_file))
        assert len(registry.get_plugins()) == 0


class TestAdapterRegistry:
    """Тесты реестра адаптеров"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.temp_dir = tempfile.mkdtemp()
        self.registry_file = Path(self.temp_dir) / "adapters_test.yaml"

        # Создаем тестовый реестр
        test_adapters = {
            "adapters": [
                {
                    "name": "kira-telegram",
                    "path": "src/kira/adapters/telegram",
                    "enabled": True,
                },
                {
                    "name": "kira-gcal",
                    "path": "src/kira/adapters/gcal",
                    "enabled": True,
                },
                {
                    "name": "kira-filesystem",
                    "path": "src/kira/adapters/filesystem",
                    "enabled": False,
                },
            ]
        }

        with open(self.registry_file, "w", encoding="utf-8") as f:
            yaml.dump(test_adapters, f)

        self.registry = AdapterRegistry(str(self.registry_file))

    def teardown_method(self):
        """Очистка после каждого теста"""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_registry(self):
        """Тест загрузки реестра"""
        adapters = self.registry.get_adapters()
        assert len(adapters) == 3
        assert adapters[0]["name"] == "kira-telegram"
        assert adapters[1]["name"] == "kira-gcal"
        assert adapters[2]["name"] == "kira-filesystem"

    def test_get_enabled_adapters(self):
        """Тест получения включенных адаптеров"""
        enabled_adapters = self.registry.get_enabled_adapters()
        assert len(enabled_adapters) == 2
        enabled_names = [a["name"] for a in enabled_adapters]
        assert "kira-telegram" in enabled_names
        assert "kira-gcal" in enabled_names
        assert "kira-filesystem" not in enabled_names

    def test_get_adapter(self):
        """Тест получения адаптера по имени"""
        adapter = self.registry.get_adapter("kira-telegram")
        assert adapter is not None
        assert adapter["name"] == "kira-telegram"
        assert adapter["path"] == "src/kira/adapters/telegram"
        assert adapter["enabled"]

        # Несуществующий адаптер
        adapter = self.registry.get_adapter("nonexistent")
        assert adapter is None

    def test_is_adapter_enabled(self):
        """Тест проверки включенности адаптера"""
        assert self.registry.is_adapter_enabled("kira-telegram") is True
        assert self.registry.is_adapter_enabled("kira-gcal") is True
        assert not self.registry.is_adapter_enabled("kira-filesystem") is True
        assert not self.registry.is_adapter_enabled("nonexistent") is True

    def test_get_adapter_path(self):
        """Тест получения пути к адаптеру"""
        path = self.registry.get_adapter_path("kira-telegram")
        assert path is not None
        assert str(path) == "src/kira/adapters/telegram"

        # Несуществующий адаптер
        path = self.registry.get_adapter_path("nonexistent")
        assert path is None


class TestRegistryIntegration:
    """Интеграционные тесты реестров"""

    def test_default_registry_files(self):
        """Тест загрузки реестров по умолчанию"""
        # Тестируем с реальными файлами в проекте
        plugin_registry = PluginRegistry()
        adapter_registry = AdapterRegistry()

        # Проверяем, что реестры загружаются без ошибок
        plugins = plugin_registry.get_plugins()
        adapters = adapter_registry.get_adapters()

        # Должны быть плагины и адаптеры из реальных файлов
        assert isinstance(plugins, list)
        assert isinstance(adapters, list)

        # Проверяем наличие ожидаемых плагинов
        plugin_names = [p.get("name") for p in plugins]
        assert "kira-inbox" in plugin_names
        assert "kira-calendar" in plugin_names

        # Проверяем наличие ожидаемых адаптеров
        adapter_names = [a.get("name") for a in adapters]
        assert "kira-telegram" in adapter_names
        assert "kira-gcal" in adapter_names
        assert "kira-filesystem" in adapter_names


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
