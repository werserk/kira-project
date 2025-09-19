"""
Реестры плагинов и адаптеров для монорепо
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class PluginRegistry:
    """Реестр плагинов"""

    def __init__(self, registry_file: str = "src/kira/registry/plugins_local.yaml"):
        self.registry_file = Path(registry_file)
        self._plugins: List[Dict[str, Any]] = []
        self._load_registry()

    def _load_registry(self):
        """Загружает реестр из YAML файла"""
        if not self.registry_file.exists():
            self._plugins = []
            return

        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self._plugins = data.get('plugins', [])
        except Exception as e:
            print(f"Ошибка загрузки реестра плагинов: {e}")
            self._plugins = []

    def get_plugins(self) -> List[Dict[str, Any]]:
        """Возвращает список всех плагинов"""
        return self._plugins.copy()

    def get_enabled_plugins(self) -> List[Dict[str, Any]]:
        """Возвращает список включенных плагинов"""
        return [p for p in self._plugins if p.get('enabled', False)]

    def get_plugin(self, name: str) -> Optional[Dict[str, Any]]:
        """Возвращает плагин по имени"""
        for plugin in self._plugins:
            if plugin.get('name') == name:
                return plugin
        return None

    def is_plugin_enabled(self, name: str) -> bool:
        """Проверяет, включен ли плагин"""
        plugin = self.get_plugin(name)
        return plugin is not None and plugin.get('enabled', False)

    def get_plugin_path(self, name: str) -> Optional[Path]:
        """Возвращает путь к плагину"""
        plugin = self.get_plugin(name)
        if plugin and 'path' in plugin:
            return Path(plugin['path'])
        return None


class AdapterRegistry:
    """Реестр адаптеров"""

    def __init__(self, registry_file: str = "src/kira/registry/adapters_local.yaml"):
        self.registry_file = Path(registry_file)
        self._adapters: List[Dict[str, Any]] = []
        self._load_registry()

    def _load_registry(self):
        """Загружает реестр из YAML файла"""
        if not self.registry_file.exists():
            self._adapters = []
            return

        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self._adapters = data.get('adapters', [])
        except Exception as e:
            print(f"Ошибка загрузки реестра адаптеров: {e}")
            self._adapters = []

    def get_adapters(self) -> List[Dict[str, Any]]:
        """Возвращает список всех адаптеров"""
        return self._adapters.copy()

    def get_enabled_adapters(self) -> List[Dict[str, Any]]:
        """Возвращает список включенных адаптеров"""
        return [a for a in self._adapters if a.get('enabled', False)]

    def get_adapter(self, name: str) -> Optional[Dict[str, Any]]:
        """Возвращает адаптер по имени"""
        for adapter in self._adapters:
            if adapter.get('name') == name:
                return adapter
        return None

    def is_adapter_enabled(self, name: str) -> bool:
        """Проверяет, включен ли адаптер"""
        adapter = self.get_adapter(name)
        return adapter is not None and adapter.get('enabled', False)

    def get_adapter_path(self, name: str) -> Optional[Path]:
        """Возвращает путь к адаптеру"""
        adapter = self.get_adapter(name)
        if adapter and 'path' in adapter:
            return Path(adapter['path'])
        return None


def get_plugin_registry() -> PluginRegistry:
    """Возвращает экземпляр реестра плагинов"""
    return PluginRegistry()


def get_adapter_registry() -> AdapterRegistry:
    """Возвращает экземпляр реестра адаптеров"""
    return AdapterRegistry()
