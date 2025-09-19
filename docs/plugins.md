# Плагинная модель Kira

## Обзор

Kira использует модульную архитектуру с плагинами для расширения функциональности. Каждый плагин имеет манифест `kira-plugin.json`, который описывает его возможности, разрешения и конфигурацию.

## Структура манифеста

### Обязательные поля

```json
{
  "name": "kira-calendar",
  "version": "0.4.2",
  "displayName": "Calendar Sync",
  "description": "Sync events & timeboxing",
  "publisher": "werserk",
  "engines": { "kira": "^1.0.0" },
  "permissions": ["calendar.write", "net", "secrets.read"],
  "entry": "kira_plugin_calendar.plugin:activate",
  "capabilities": ["pull", "push", "timebox"],
  "contributes": {
    "events": ["event.created", "task.due_soon"],
    "commands": ["calendar.pull", "calendar.push"]
  }
}
```

### Разрешения

- `calendar.read/write` - доступ к календарю
- `vault.read/write` - доступ к хранилищу
- `fs.read/write` - доступ к файловой системе
- `net` - сетевой доступ
- `secrets.read/write` - доступ к секретам
- `events.publish/subscribe` - работа с событиями
- `scheduler.create/cancel` - планировщик
- `sandbox.execute` - выполнение в песочнице

### Возможности

- `pull` - получение данных
- `push` - отправка данных
- `timebox` - работа с временными блоками
- `notify` - уведомления
- `schedule` - планирование
- `transform` - преобразование данных
- `validate` - валидация
- `sync` - синхронизация

## Валидация манифеста

### Python API

```python
from kira.plugin_sdk.manifest import PluginManifestValidator

validator = PluginManifestValidator()
errors = validator.validate_manifest_file("path/to/kira-plugin.json")

if errors:
    for error in errors:
        print(f"Ошибка: {error}")
else:
    print("Манифест валиден!")
```

### Быстрая проверка

```python
from kira.plugin_sdk.manifest import validate_plugin_manifest

is_valid = validate_plugin_manifest(manifest_data)
```

## Конфигурация плагина

Плагины могут определять схему своей конфигурации:

```json
{
  "configSchema": {
    "calendar.default": {
      "type": "string",
      "description": "Default calendar ID"
    },
    "timebox.length": {
      "type": "integer",
      "default": 90,
      "minimum": 15,
      "maximum": 480
    },
    "notifications.enabled": {
      "type": "boolean",
      "default": true
    }
  }
}
```

## Изоляция плагинов

### Стратегии изоляции

- `subprocess` - отдельный процесс (по умолчанию)
- `thread` - отдельный поток
- `inline` - выполнение в основном потоке

### Конфигурация песочницы

```json
{
  "sandbox": {
    "strategy": "subprocess",
    "timeoutMs": 60000,
    "memoryLimit": 128,
    "networkAccess": true,
    "fsAccess": {
      "read": ["/tmp"],
      "write": ["/tmp/plugin"]
    }
  }
}
```

## Создание плагина

1. Создайте директорию для плагина
2. Добавьте `kira-plugin.json` с манифестом
3. Реализуйте точку входа в указанном модуле
4. Протестируйте валидацию манифеста

### Пример структуры

```
my-plugin/
├── kira-plugin.json
├── src/
│   └── my_plugin/
│       ├── __init__.py
│       └── plugin.py
└── README.md
```

## SDK для плагинов

Плагины получают доступ к функциональности через `PluginContext`:

```python
from kira.plugin_sdk.context import PluginContext
from kira.plugin_sdk.decorators import on_event, command

def activate(context: PluginContext):
    # Инициализация плагина
    pass

@on_event("event.created")
def handle_event(context: PluginContext, event_data):
    # Обработка события
    pass

@command("my.command")
def my_command(context: PluginContext, args):
    # Обработка команды
    pass
```

## Тестирование

Используйте встроенные тесты для проверки валидации:

```bash
python -m pytest tests/unit/test_manifest_schema.py
```
