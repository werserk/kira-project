"""
Plugin Context - контекст выполнения плагина
"""
from pathlib import Path
from typing import Any, Dict, List, Optional


class PluginContext:
    """Контекст выполнения плагина"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.events = EventBus()
        self.logger = Logger()
        self.scheduler = Scheduler()
        self.kv = KeyValueStore()
        self.secrets = SecretsManager()


class EventBus:
    """Шина событий для плагинов"""

    def __init__(self):
        self._subscribers = {}

    def publish(self, event_name: str, data: Dict[str, Any]) -> None:
        """Публикует событие"""
        print(f"📢 Событие: {event_name}")
        if data:
            print(f"   Данные: {data}")

    def subscribe(self, event_name: str, handler) -> None:
        """Подписывается на событие"""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(handler)


class Logger:
    """Логгер для плагинов"""

    def info(self, message: str) -> None:
        """Информационное сообщение"""
        print(f"ℹ️  {message}")

    def warning(self, message: str) -> None:
        """Предупреждение"""
        print(f"⚠️  {message}")

    def error(self, message: str) -> None:
        """Ошибка"""
        print(f"❌ {message}")

    def debug(self, message: str) -> None:
        """Отладочное сообщение"""
        print(f"🐛 {message}")


class Scheduler:
    """Планировщик для плагинов"""

    def schedule_once(self, delay_seconds: int, task) -> str:
        """Планирует выполнение задачи один раз"""
        task_id = f"task_{delay_seconds}"
        print(f"⏰ Запланирована задача: {task_id}")
        return task_id

    def schedule_recurring(self, interval_seconds: int, task) -> str:
        """Планирует повторяющуюся задачу"""
        task_id = f"recurring_{interval_seconds}"
        print(f"🔄 Запланирована повторяющаяся задача: {task_id}")
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Отменяет задачу"""
        print(f"❌ Задача отменена: {task_id}")
        return True


class KeyValueStore:
    """Хранилище ключ-значение для плагинов"""

    def __init__(self):
        self._store = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Получает значение по ключу"""
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Устанавливает значение по ключу"""
        self._store[key] = value
        print(f"💾 Сохранено: {key} = {value}")

    def delete(self, key: str) -> bool:
        """Удаляет значение по ключу"""
        if key in self._store:
            del self._store[key]
            print(f"🗑️  Удалено: {key}")
            return True
        return False


class SecretsManager:
    """Менеджер секретов для плагинов"""

    def get(self, key: str) -> Optional[str]:
        """Получает секрет по ключу"""
        # В реальной реализации здесь будет обращение к хранилищу секретов
        print(f"🔐 Запрошен секрет: {key}")
        return f"secret_value_for_{key}"

    def set(self, key: str, value: str) -> None:
        """Устанавливает секрет"""
        print(f"🔐 Секрет установлен: {key}")

    def delete(self, key: str) -> bool:
        """Удаляет секрет"""
        print(f"🔐 Секрет удален: {key}")
        return True
