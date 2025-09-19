# Inbox Normalizer Plugin

## Описание

Inbox Normalizer - это встроенный плагин Kira, который нормализует входящие сообщения и файлы, извлекает метаданные и создает структурированные Markdown файлы.

## Возможности

- **Нормализация текста**: Очистка от лишних пробелов, нормализация переносов строк
- **Извлечение метаданных**: Автоматическое определение типа контента, приоритета, тегов
- **Создание структурированных файлов**: Markdown с frontmatter для удобной обработки
- **Обработка событий**: Реагирование на события `message.received` и `file.dropped`
- **Команды**: Предоставляет команду `inbox.normalize` для ручной нормализации

## Манифест плагина

```json
{
  "name": "kira-inbox",
  "version": "0.1.0",
  "displayName": "Inbox Normalizer",
  "description": "Normalizes incoming messages and files, extracts metadata and creates structured Markdown files",
  "publisher": "kira",
  "engines": { "kira": "^1.0.0" },
  "permissions": [],
  "entry": "kira_plugin_inbox.plugin:activate",
  "capabilities": ["normalize"],
  "contributes": {
    "events": ["message.received","file.dropped"],
    "commands": ["inbox.normalize"]
  },
  "sandbox": { "strategy": "subprocess", "timeoutMs": 20000 }
}
```

## Использование

### Автоматическая обработка

Плагин автоматически обрабатывает события:

```python
# Событие получения сообщения
{
    "message": "# Важная задача\n\nНужно сделать что-то срочно! #работа #срочно",
    "source": "telegram"
}

# Событие сброса файла
{
    "file_path": "/path/to/inbox/note.txt"
}
```

### Ручная нормализация

```python
# Через команду
result = normalize_command(context, ['Встреча', 'завтра', 'в', '15:00', '#встреча'])
```

### Через CLI

```bash
# Нормализация через команду
./kira ext info kira-inbox

# Обработка inbox через pipeline
make inbox
```

## Типы контента

Плагин автоматически определяет тип контента:

- **note** - начинается с `#`
- **task** - содержит ключевые слова: "задача", "task", "todo"
- **event** - содержит ключевые слова: "встреча", "meeting", "call"
- **link** - начинается с `http`
- **text** - по умолчанию

## Приоритеты

- **high** - содержит: "срочно", "urgent", "важно"
- **low** - содержит: "низкий", "low"
- **medium** - по умолчанию

## Извлечение тегов

Плагин автоматически извлекает теги в формате `#тег` из текста.

## Структура выходных файлов

Создаваемые файлы имеют следующую структуру:

```markdown
---
{
  "title": "Краткое описание",
  "created": "2024-01-01T12:00:00",
  "source": "telegram",
  "type": "note",
  "priority": "high",
  "tags": ["работа", "срочно"],
  "length": 60
}
---

# Краткое описание

Оригинальный контент...

---
*Обработано плагином Inbox Normalizer*
```

## События

### Публикуемые события

- `plugin.activated` - плагин активирован
- `inbox.normalized` - элемент нормализован

### Обрабатываемые события

- `message.received` - получено сообщение
- `file.dropped` - сброшен файл

## API

### InboxNormalizer

```python
class InboxNormalizer:
    def normalize_text(self, text: str) -> str
    def extract_metadata(self, content: str, source: str = None) -> Dict[str, Any]
    def create_normalized_file(self, content: str, metadata: Dict[str, Any]) -> Path
    def process_message(self, message: str, source: str = None) -> Dict[str, Any]
    def process_file(self, file_path: Path) -> Dict[str, Any]
```

### Декораторы

```python
@on_event('message.received')
def handle_message_received(context: PluginContext, event_data: Dict[str, Any]) -> None

@on_event('file.dropped')
def handle_file_dropped(context: PluginContext, event_data: Dict[str, Any]) -> None

@command('inbox.normalize')
def normalize_command(context: PluginContext, args: List[str]) -> str
```

## Конфигурация

Плагин использует конфигурацию Vault:

```yaml
vault:
  path: "/path/to/vault"  # Путь к Vault
```

Создаются директории:
- `{vault_path}/inbox/` - для входящих файлов
- `{vault_path}/processed/` - для обработанных файлов

## Тестирование

```bash
# Запуск демонстрации
python3 demo_inbox_plugin.py

# Запуск тестов
python3 tests/unit/test_inbox_plugin.py
```

## Примеры

### Обработка сообщения

```python
from kira.plugin_sdk.context import PluginContext
from kira.plugins.inbox.src.kira_plugin_inbox.plugin import activate, handle_message_received

# Активация плагина
context = PluginContext(config)
activate(context)

# Обработка сообщения
event_data = {
    'message': '# Задача\n\nСделать что-то важное #работа',
    'source': 'telegram'
}
handle_message_received(context, event_data)
```

### Обработка файла

```python
from pathlib import Path

# Создание файла
file_path = Path('/tmp/inbox/note.txt')
file_path.write_text('Содержимое файла #заметка')

# Обработка файла
event_data = {'file_path': str(file_path)}
handle_file_dropped(context, event_data)
```

## Разработка

### Структура файлов

```
src/kira/plugins/inbox/
├── kira-plugin.json                    # Манифест плагина
├── README.md                           # Документация
└── src/kira_plugin_inbox/
    ├── __init__.py
    └── plugin.py                       # Основная логика
```

### Добавление новых типов контента

```python
def extract_metadata(self, content: str, source: str = None) -> Dict[str, Any]:
    # Добавить новый тип
    if 'новый_тип' in content.lower():
        metadata['type'] = 'new_type'
```

### Добавление новых приоритетов

```python
def extract_metadata(self, content: str, source: str = None) -> Dict[str, Any]:
    # Добавить новый приоритет
    if 'критично' in content.lower():
        metadata['priority'] = 'critical'
```

## Логирование

Плагин использует стандартный логгер Kira:

```python
context.logger.info("Сообщение нормализовано")
context.logger.error("Ошибка нормализации")
```

## Производительность

- Таймаут выполнения: 20 секунд
- Стратегия изоляции: subprocess
- Обработка файлов: потоковая
- Память: минимальное использование
