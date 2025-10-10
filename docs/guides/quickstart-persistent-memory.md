# Быстрый старт: Персистентная память

## 🎉 Кира теперь помнит разговоры!

После интеграции Phase 1 Kira сохраняет историю диалогов в SQLite и помнит контекст даже после перезапуска.

---

## Как протестировать

### 1. Запустить Telegram бота

```bash
# Убедитесь, что настройки уже в .env (добавлены автоматически)
kira telegram start
```

Или через Docker:

```bash
make telegram-start
```

### 2. Проверить память

**Первый запрос:**
```
Вы: Привет! Меня зовут Максим
Кира: Приятно познакомиться, Максим! Чем могу помочь?
```

**Второй запрос (в той же сессии):**
```
Вы: Как меня зовут?
Кира: Вас зовут Максим! 👍
```

**Перезапустите бота:**
```bash
# Ctrl+C
kira telegram start
```

**Третий запрос (после перезапуска):**
```
Вы: Что я спросил в предыдущем вопросе?
Кира: В предыдущем вопросе вы спросили "Как меня зовут?"
```

✅ **Работает!** Память сохранилась после перезапуска.

---

## Что добавлено

### Новые файлы:
- ✅ `src/kira/agent/persistent_memory.py` - SQLite память
- ✅ `tests/unit/test_persistent_memory.py` - Тесты (100% покрытие)
- ✅ `docs/guides/persistent-memory.md` - Полная документация

### Измененные файлы:
- ✅ `src/kira/agent/langgraph_executor.py` - Интеграция памяти
- ✅ `src/kira/agent/unified_executor.py` - Передача параметров
- ✅ `src/kira/agent/config.py` - Новые настройки
- ✅ `src/kira/config/settings.py` - Загрузка из .env
- ✅ `.env` - Добавлены параметры
- ✅ `CHANGELOG.md` - Документирование изменений

---

## Настройки в `.env`

```bash
# Persistent Memory (survives restarts)
ENABLE_PERSISTENT_MEMORY=true
MEMORY_DB_PATH=artifacts/conversations.db

# Maximum exchanges to keep per session
MEMORY_MAX_EXCHANGES=10
```

**По умолчанию:** Включена персистентная память с 10 обменами на сессию.

---

## Проверить работу памяти

### Через Python API:

```python
from pathlib import Path
from kira.agent.persistent_memory import PersistentConversationMemory

# Создать или подключиться к существующей базе
memory = PersistentConversationMemory(
    db_path=Path("artifacts/conversations.db"),
    max_exchanges=10,
)

# Проверить количество сессий
print(f"Active sessions: {memory.get_session_count()}")

# Список всех сессий
sessions = memory.get_all_sessions()
for session_id in sessions:
    print(f"Session: {session_id}")
    turns = memory.get_turns(session_id)
    print(f"  Turns: {len(turns)}")

# Экспорт сессии
export = memory.export_session("telegram:123456789")
print(export)
```

### Через SQLite:

```bash
# Посмотреть базу данных
sqlite3 artifacts/conversations.db

# SQL запросы
SELECT session_id, COUNT(*) as messages
FROM conversations
GROUP BY session_id;

SELECT role, content, timestamp
FROM conversations
WHERE session_id = 'telegram:123456'
ORDER BY timestamp;
```

---

## Тесты

```bash
# Запустить unit тесты
pytest tests/unit/test_persistent_memory.py -v

# С покрытием
pytest tests/unit/test_persistent_memory.py --cov=kira.agent.persistent_memory --cov-report=html

# Все тесты агента
pytest tests/unit/test_agent*.py tests/unit/test_persistent_memory.py
```

**Ожидаемый результат:**
```
tests/unit/test_persistent_memory.py::test_initialization PASSED
tests/unit/test_persistent_memory.py::test_add_turn PASSED
tests/unit/test_persistent_memory.py::test_get_context_messages PASSED
tests/unit/test_persistent_memory.py::test_persistence_across_instances PASSED
...
======================== 24 passed in 0.5s =========================
```

---

## Отключить персистентную память

Если хотите вернуться к эфемерной (RAM-only) памяти:

```bash
# В .env
ENABLE_PERSISTENT_MEMORY=false
```

Или программно:

```python
from kira.agent.langgraph_executor import LangGraphExecutor

executor = LangGraphExecutor(
    llm_adapter=llm,
    tool_registry=registry,
    enable_persistent_memory=False,  # ← Эфемерная
    memory_max_exchanges=3,
)
```

---

## Troubleshooting

### База повреждена

```bash
rm artifacts/conversations.db
kira telegram start
```

### Слишком большая база

```bash
# Проверить размер
du -h artifacts/conversations.db

# Очистить старые сессии (будет автоматизировано в Phase 2)
sqlite3 artifacts/conversations.db "DELETE FROM conversations WHERE session_id = 'old_session';"
```

### Память не работает

```python
# Проверить настройки
from kira.config.settings import load_settings
settings = load_settings()
print(f"Persistent: {settings.enable_persistent_memory}")
print(f"DB: {settings.memory_db_path}")
print(f"Max: {settings.memory_max_exchanges}")
```

---

## Следующие шаги (Phase 2-3)

- 🔄 Автоматическая очистка старых сессий (TTL)
- 📊 Аналитика использования памяти
- 🧠 Long-term memory в vault (Obsidian-compatible)
- 🔍 Семантический поиск по истории

---

## Документация

- **Полная документация**: `docs/guides/persistent-memory.md`
- **Код**: `src/kira/agent/persistent_memory.py`
- **Тесты**: `tests/unit/test_persistent_memory.py`

---

**Статус:** ✅ Готово к использованию
**Версия:** 0.1.0-alpha
**Дата:** 2025-10-10

