"""
Реестры плагинов и адаптеров для монорепо
"""

from pathlib import Path
from typing import Any

import yaml


class PluginRegistry:
    """Реестр плагинов"""

    def __init__(
        self,
        registry_file: str = "src/kira/registry/plugins_local.yaml",
        config_file: str = "kira.yaml",
    ) -> None:
        self.registry_file = Path(registry_file)
        self.config_file = Path(config_file)
        self._plugins: list[dict[str, Any]] = []
        self._enabled_plugins: list[str] = []
        self._load_registry()
        self._load_config()

    def _load_registry(self) -> None:
        """Загружает реестр из YAML файла"""
        if not self.registry_file.exists():
            self._plugins = []
            return

        try:
            with open(self.registry_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self._plugins = data.get("plugins", [])
        except Exception as e:
            print(f"Ошибка загрузки реестра плагинов: {e}")
            self._plugins = []

    def _load_config(self) -> None:
        """Загружает конфигурацию для определения enabled плагинов"""
        if not self.config_file.exists():
            self._enabled_plugins = []
            return

        try:
            with open(self.config_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "plugins" in data and "enabled" in data["plugins"]:
                    self._enabled_plugins = data["plugins"]["enabled"]
                else:
                    self._enabled_plugins = []
        except Exception as e:
            print(f"Ошибка загрузки конфигурации плагинов: {e}")
            self._enabled_plugins = []

    def get_plugins(self) -> list[dict[str, Any]]:
        """Возвращает список всех плагинов"""
        return self._plugins.copy()

    def get_enabled_plugins(self) -> list[dict[str, Any]]:
        """Возвращает список включенных плагинов (из kira.yaml или поля enabled в реестре)"""
        result = []
        for p in self._plugins:
            # Если в самом плагине есть поле enabled, используем его (для тестов)
            if "enabled" in p:
                if p["enabled"]:
                    result.append(p)
            # Иначе проверяем список включенных плагинов из kira.yaml
            elif p.get("name") in self._enabled_plugins:
                result.append(p)
        return result

    def get_plugin(self, name: str) -> dict[str, Any] | None:
        """Возвращает плагин по имени"""
        for plugin in self._plugins:
            if plugin.get("name") == name:
                return plugin
        return None

    def is_plugin_enabled(self, name: str) -> bool:
        """Проверяет, включен ли плагин (проверяет kira.yaml или поле enabled в реестре)"""
        # Проверяем что плагин зарегистрирован
        plugin = self.get_plugin(name)
        if plugin is None:
            return False
        # Если в самом плагине есть поле enabled, используем его (для тестов)
        if "enabled" in plugin:
            return plugin["enabled"]
        # Иначе проверяем список включенных плагинов из kira.yaml
        return name in self._enabled_plugins

    def get_plugin_path(self, name: str) -> Path | None:
        """Возвращает путь к плагину"""
        plugin = self.get_plugin(name)
        if plugin and "path" in plugin:
            return Path(plugin["path"])
        return None


class AdapterRegistry:
    """Реестр адаптеров"""

    def __init__(
        self,
        registry_file: str = "src/kira/registry/adapters_local.yaml",
        config_file: str = "kira.yaml",
    ) -> None:
        self.registry_file = Path(registry_file)
        self.config_file = Path(config_file)
        self._adapters: list[dict[str, Any]] = []
        self._enabled_adapters: dict[str, bool] = {}
        self._load_registry()
        self._load_config()

    def _load_registry(self) -> None:
        """Загружает реестр из YAML файла"""
        if not self.registry_file.exists():
            self._adapters = []
            return

        try:
            with open(self.registry_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self._adapters = data.get("adapters", [])
        except Exception as e:
            print(f"Ошибка загрузки реестра адаптеров: {e}")
            self._adapters = []

    def _load_config(self) -> None:
        """Загружает конфигурацию для определения enabled адаптеров"""
        if not self.config_file.exists():
            self._enabled_adapters = {}
            return

        try:
            with open(self.config_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "adapters" in data:
                    adapters_config = data["adapters"]
                    # Проверяем telegram, gcal и другие адаптеры
                    for adapter_name, adapter_config in adapters_config.items():
                        if isinstance(adapter_config, dict) and "enabled" in adapter_config:
                            # Маппинг имен: telegram -> kira-telegram, gcal -> kira-gcal
                            full_name = f"kira-{adapter_name}"
                            self._enabled_adapters[full_name] = adapter_config["enabled"]
                else:
                    self._enabled_adapters = {}
        except Exception as e:
            print(f"Ошибка загрузки конфигурации адаптеров: {e}")
            self._enabled_adapters = {}

    def get_adapters(self) -> list[dict[str, Any]]:
        """Возвращает список всех адаптеров"""
        return self._adapters.copy()

    def get_enabled_adapters(self) -> list[dict[str, Any]]:
        """Возвращает список включенных адаптеров (из kira.yaml)"""
        result = []
        for adapter in self._adapters:
            name = adapter.get("name")
            if name and self._enabled_adapters.get(name, False):
                result.append(adapter)
        return result

    def get_adapter(self, name: str) -> dict[str, Any] | None:
        """Возвращает адаптер по имени"""
        for adapter in self._adapters:
            if adapter.get("name") == name:
                return adapter
        return None

    def is_adapter_enabled(self, name: str) -> bool:
        """Проверяет, включен ли адаптер (проверяет kira.yaml)"""
        # Проверяем что адаптер зарегистрирован
        adapter = self.get_adapter(name)
        if adapter is None:
            return False
        # Проверяем что адаптер включен в конфигурации
        return self._enabled_adapters.get(name, False)

    def get_adapter_path(self, name: str) -> Path | None:
        """Возвращает путь к адаптеру"""
        adapter = self.get_adapter(name)
        if adapter and "path" in adapter:
            return Path(adapter["path"])
        return None


def get_plugin_registry() -> PluginRegistry:
    """Возвращает экземпляр реестра плагинов"""
    return PluginRegistry()


def get_adapter_registry() -> AdapterRegistry:
    """Возвращает экземпляр реестра адаптеров"""
    return AdapterRegistry()
