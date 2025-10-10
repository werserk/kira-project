# Persistent Conversation Memory

**Status:** ✅ Implemented (Phase 1)
**Version:** 0.1.0-alpha
**Date:** 2025-10-10

## Overview

Kira теперь поддерживает **персистентную память разговоров**, которая сохраняется между перезапусками бота. Это решает проблему "забывчивости" Киры и позволяет вести длительные диалоги с контекстом.

## Проблема

**До Phase 1:**
- Память хранилась только в RAM (эфемерная)
- При перезапуске Docker/бота всё терялось
- Кира не помнила предыдущие сообщения после restart

**После Phase 1:**
- Память сохраняется в SQLite (`artifacts/conversations.db`)
- Выдерживает перезапуски
- История разговора доступна при следующем запуске

---

## Архитектура

### Три уровня памяти (будущее):

```
┌─────────────────────────────────────────────────────┐
│  Level 1: Short-term (in-memory cache)              │
│  Scope: Последние 3-5 обменов                       │
│  Storage: RAM (deque)                               │
│  Use case: Быстрый доступ для текущего диалога     │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Level 2: Medium-term (SQLite) ✅ РЕАЛИЗОВАНО       │
│  Scope: До 50 обменов на сессию                     │
│  Storage: SQLite (artifacts/conversations.db)       │
│  Use case: История чата, выживает перезапуск        │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Level 3: Long-term (Vault) 🚧 БУДУЩЕЕ              │
│  Scope: Важные факты, предпочтения                  │
│  Storage: Markdown в vault/memory/                  │
│  Use case: Долгосрочный контекст, Obsidian-совместим│
└─────────────────────────────────────────────────────┘
```

**Phase 1 реализует Level 2 (Medium-term SQLite memory).**

---

## Конфигурация

### `.env` настройки

```bash
# Persistent Memory (survives restarts)
ENABLE_PERSISTENT_MEMORY=true
MEMORY_DB_PATH=artifacts/conversations.db

# Maximum exchanges to keep per session
MEMORY_MAX_EXCHANGES=10
```

### Параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `ENABLE_PERSISTENT_MEMORY` | bool | `true` | Включить SQLite персистентность |
| `MEMORY_DB_PATH` | Path | `artifacts/conversations.db` | Путь к базе данных |
| `MEMORY_MAX_EXCHANGES` | int | `10` | Максимум обменов на сессию |

---

## Использование

### Автоматическое использование

Персистентная память **включена по умолчанию** и работает автоматически:

```bash
# Запуск Telegram бота
kira telegram start

# Или через Docker
make telegram-start
```

Кира будет:
1. Загружать историю при старте
2. Сохранять каждый обмен в SQLite
3. Использовать контекст при ответе

### Программное использование

```python
from pathlib import Path
from kira.agent.persistent_memory import PersistentConversationMemory

# Создать память
memory = PersistentConversationMemory(
    db_path=Path("artifacts/conversations.db"),
    max_exchanges=50,
)

# Добавить разговор
memory.add_turn(
    session_id="telegram:123456",
    user_message="Какая погода?",
    assistant_message="Солнечно, +15°C",
    metadata={"timestamp": "2025-10-10T10:00:00Z"},
)

# Получить историю
messages = memory.get_context_messages("telegram:123456")
for msg in messages:
    print(f"{msg.role}: {msg.content}")

# Экспорт для backup
export = memory.export_session("telegram:123456")
```

---

## Как это работает

### 1. Session ID

Каждый чат имеет уникальный `session_id`:

```python
# Telegram: "telegram:{chat_id}"
session_id = "telegram:123456789"

# CLI: "cli:{user}"
session_id = "cli:default"

# HTTP API: "api:{user_id}"
session_id = "api:user-42"
```

### 2. Хранение

Разговоры сохраняются в SQLite:

```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    role TEXT NOT NULL,        -- 'user' or 'assistant'
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP
);

CREATE INDEX idx_session_timestamp
ON conversations(session_id, timestamp DESC);
```

### 3. Жизненный цикл

```
User Message
     ↓
[Telegram Adapter]
     ↓
session_id = "telegram:{chat_id}"
     ↓
[LangGraphExecutor]
     ↓
memory.get_context_messages(session_id)  ← Загружаем историю
     ↓
[LLM с контекстом]
     ↓
[Generate Response]
     ↓
memory.add_turn(session_id, user_msg, assistant_msg)  ← Сохраняем
     ↓
[Send to Telegram]
```

### 4. Кэширование

Для производительности используется двухуровневое хранение:

- **Cache (RAM)**: Последние 10 обменов
- **Database (SQLite)**: Полная история

При запросе:
1. Проверяем кэш
2. Если нет → загружаем из SQLite
3. Обновляем кэш

---

## API Reference

### `PersistentConversationMemory`

```python
class PersistentConversationMemory:
    """Conversation memory with SQLite persistence."""

    def __init__(
        self,
        db_path: Path,
        max_exchanges: int = 50,
        cache_size: int = 10,
    ):
        """Initialize persistent memory."""

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add conversation turn."""

    def get_context_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[Message]:
        """Get context messages for session."""

    def get_turns(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[ConversationTurn]:
        """Get conversation turns."""

    def clear_session(self, session_id: str) -> None:
        """Clear session memory."""

    def has_context(self, session_id: str) -> bool:
        """Check if session has context."""

    def get_session_count(self) -> int:
        """Get total number of active sessions."""

    def get_all_sessions(self) -> list[str]:
        """Get list of all session IDs."""

    def export_session(self, session_id: str) -> dict[str, Any]:
        """Export session data for backup."""
```

---

## Примеры

### Пример 1: Базовое использование

```python
from kira.agent.persistent_memory import PersistentConversationMemory
from pathlib import Path

memory = PersistentConversationMemory(
    db_path=Path("artifacts/conversations.db"),
    max_exchanges=10,
)

# Первая сессия
memory.add_turn("user1", "Привет!", "Привет! Как дела?")
memory.add_turn("user1", "Отлично", "Рад слышать!")

# Вторая сессия
memory.add_turn("user2", "Hello", "Hi there!")

# Получить историю
messages_user1 = memory.get_context_messages("user1")
print(f"User1 has {len(messages_user1)} messages")
# Output: User1 has 4 messages

messages_user2 = memory.get_context_messages("user2")
print(f"User2 has {len(messages_user2)} messages")
# Output: User2 has 2 messages
```

### Пример 2: Экспорт и backup

```python
# Экспорт всех сессий
all_sessions = memory.get_all_sessions()
backup_data = {}

for session_id in all_sessions:
    backup_data[session_id] = memory.export_session(session_id)

# Сохранить в JSON
import json
with open("backup/conversations.json", "w") as f:
    json.dump(backup_data, f, indent=2)

print(f"Backed up {len(all_sessions)} sessions")
```

### Пример 3: Очистка старых сессий

```python
# Очистить сессию
memory.clear_session("telegram:123456")

# Проверить
if not memory.has_context("telegram:123456"):
    print("Session cleared successfully")
```

### Пример 4: Интеграция с агентом

```python
from kira.agent.langgraph_executor import LangGraphExecutor
from kira.adapters.llm import create_llm_adapter
from kira.agent.tools import ToolRegistry

llm = create_llm_adapter("openrouter", api_key="...")
registry = ToolRegistry()

# Создать executor с персистентной памятью
executor = LangGraphExecutor(
    llm_adapter=llm,
    tool_registry=registry,
    enable_persistent_memory=True,  # ← Включаем
    memory_db_path=Path("artifacts/conversations.db"),
    memory_max_exchanges=50,
)

# Первый запрос
result1 = executor.execute(
    "Меня зовут Максим",
    session_id="telegram:123",
)
print(result1.response)
# Output: "Приятно познакомиться, Максим!"

# Второй запрос (в той же сессии)
result2 = executor.execute(
    "Как меня зовут?",
    session_id="telegram:123",
)
print(result2.response)
# Output: "Вас зовут Максим" ← Помнит!
```

---

## Миграция с эфемерной памяти

### Если у вас была старая версия

Обновление **автоматическое**. При первом запуске:

1. Создается `artifacts/conversations.db`
2. Новые разговоры сохраняются в SQLite
3. Старые разговоры (в RAM) будут потеряны при restart

**Никакой миграции данных не требуется.**

### Отключить персистентную память

Если хотите вернуться к эфемерной:

```bash
# В .env
ENABLE_PERSISTENT_MEMORY=false
```

Или в коде:

```python
executor = LangGraphExecutor(
    llm_adapter=llm,
    tool_registry=registry,
    enable_persistent_memory=False,  # ← Эфемерная память
    memory_max_exchanges=3,
)
```

---

## Troubleshooting

### База данных повреждена

```bash
# Удалить и пересоздать
rm artifacts/conversations.db

# Перезапустить бота
kira telegram start
```

### Слишком много данных

```bash
# Проверить размер базы
du -h artifacts/conversations.db

# Если > 100MB, очистить старые сессии
# (автоматическая очистка будет добавлена в Phase 2)
```

### Память не работает

Проверьте настройки:

```python
from kira.config.settings import load_settings

settings = load_settings()
print(f"Persistent memory: {settings.enable_persistent_memory}")
print(f"DB path: {settings.memory_db_path}")
print(f"Max exchanges: {settings.memory_max_exchanges}")
```

---

## Performance

### Бенчмарки

| Operation | Ephemeral (RAM) | Persistent (SQLite) |
|-----------|-----------------|---------------------|
| Add turn | 0.001ms | 1-2ms |
| Get context (cache hit) | 0.01ms | 0.01ms |
| Get context (cache miss) | - | 5-10ms |
| Session with 50 exchanges | N/A | ~100KB |

**Вывод:** Minimal overhead (1-2ms per message), незаметно для пользователя.

---

## Roadmap

### Phase 2 (будущее)

- 🔄 Автоматическая очистка старых сессий (TTL)
- 📊 Аналитика использования памяти
- 🔍 Полнотекстовый поиск по истории
- 📤 Экспорт в Markdown для Obsidian

### Phase 3 (будущее)

- 🧠 Long-term memory (vault-based)
- 🔗 Семантический поиск с векторными embeddings
- 🎯 Извлечение важных фактов из диалогов
- 📝 Ручное редактирование через Obsidian

---

## Testing

```bash
# Запустить тесты
pytest tests/unit/test_persistent_memory.py -v

# С покрытием
pytest tests/unit/test_persistent_memory.py --cov=kira.agent.persistent_memory

# Интеграционные тесты
pytest tests/integration/test_agent_langgraph_e2e.py -k memory
```

---

## References

- **Код**: `src/kira/agent/persistent_memory.py`
- **Тесты**: `tests/unit/test_persistent_memory.py`
- **Конфигурация**: `.env`, `src/kira/config/settings.py`
- **Интеграция**: `src/kira/agent/langgraph_executor.py`

---

## Вклад в проект

При добавлении новых фич для памяти:

1. ✅ Поддерживайте обратную совместимость
2. ✅ Добавляйте тесты (95% coverage)
3. ✅ Документируйте в этом файле
4. ✅ Следуйте паттерну Session ID

---

**Version:** 1.0
**Last Updated:** 2025-10-10
**Maintainer:** Kira Development Team

