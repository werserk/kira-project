# Telegram Integration Architecture

**Status:** ✅ Unified and Production-Ready
**Last Updated:** 2025-10-08

---

## Overview

Kira теперь имеет **унифицированную архитектуру** для интеграции Telegram с AI агентом. Два подхода (polling и webhook) правильно разделены и не дублируют функциональность.

---

## 🏗️ Architecture

### Mode 1: Long Polling (Development & No Public URL)

**Use Case:** Локальная разработка, серверы без публичного IP

```
┌─────────┐     ┌──────────────────┐     ┌──────────┐     ┌──────────────┐     ┌─────────────┐
│ Telegram│────▶│ TelegramAdapter  │────▶│ EventBus │────▶│MessageHandler│────▶│AgentExecutor│
│   Bot   │◀────│   (long polling) │◀────│          │◀────│              │◀────│             │
└─────────┘     └──────────────────┘     └──────────┘     └──────────────┘     └─────────────┘
```

**Components:**
- **TelegramAdapter** - Polling Telegram API, публикует события
- **EventBus** - In-process event bus (pub/sub)
- **MessageHandler** - Подписчик, который вызывает Agent и отправляет ответы
- **AgentExecutor** - AI Agent с LLM, tools, RAG, memory

**Files:**
- `src/kira/adapters/telegram/adapter.py` - TelegramAdapter
- `src/kira/agent/message_handler.py` - MessageHandler ✨ NEW
- `src/kira/cli/kira_telegram.py` - CLI команда `kira telegram start`

**Launch:**
```bash
kira telegram start --token YOUR_TOKEN
```

---

### Mode 2: Webhook (Production with Public HTTPS)

**Use Case:** Production deployment с публичным HTTPS endpoint

```
┌─────────┐     ┌────────────────┐     ┌─────────────┐
│ Telegram│────▶│ TelegramGateway│────▶│AgentExecutor│
│   Bot   │◀────│  (FastAPI POST)│◀────│             │
└─────────┘     └────────────────┘     └─────────────┘
```

**Components:**
- **TelegramGateway** - FastAPI router для webhook
- **AgentExecutor** - Прямой вызов без Event Bus

**Files:**
- `src/kira/agent/telegram_gateway.py` - Webhook integration
- `src/kira/agent/service.py` - FastAPI app с интеграцией

**Launch:**
```bash
# Start FastAPI server
kira agent serve

# Configure webhook in Telegram
curl -X POST https://your-domain.com/telegram/webhook \
  -H "Content-Type: application/json"
```

---

## ✅ What Was Fixed

### Problem: Two Disconnected Approaches

**Before:**
1. TelegramAdapter публиковал события, но **никто не вызывал Agent**
2. TelegramGateway работал только для webhook
3. `kira telegram start` запускал polling, но сообщения **не обрабатывались агентом**

### Solution: Unified Event-Driven Architecture

**After:**
1. ✅ **MessageHandler** создан - связывает Event Bus → AgentExecutor
2. ✅ **CLI интеграция** - `kira telegram start` теперь запускает полный стек
3. ✅ **Response callback** - ответы агента автоматически отправляются в Telegram
4. ✅ **Documentation** - чёткое разделение webhook vs polling
5. ✅ **Tests** - 15 unit тестов для MessageHandler

---

## 🧪 Testing

### New Tests

**File:** `tests/unit/test_message_handler.py`

```bash
# Run message handler tests
make test ARGS="tests/unit/test_message_handler.py -v"
```

**Test Coverage:**
- ✅ Successful message handling
- ✅ Error handling and exceptions
- ✅ Empty messages and missing payloads
- ✅ Multiple execution steps
- ✅ Response formatting
- ✅ Trace ID generation
- ✅ Dict summarization

**Results:** All 15 tests passing ✅

---

## 📝 Configuration

### kira.yaml Example

```yaml
vault:
  path: ./vault

agent:
  enable_rag: true
  memory_max_exchanges: 10
  default_dry_run: true
  enable_ollama_fallback: true

adapters:
  telegram:
    mode: bot
    whitelist_chats:
      - 123456789
    polling_timeout: 30
    daily_briefing_time: "09:00"
```

### Environment Variables

```bash
# Telegram
export TELEGRAM_BOT_TOKEN="your_bot_token"

# LLM Providers
export ANTHROPIC_API_KEY="your_key"
export OPENAI_API_KEY="your_key"
export OPENROUTER_API_KEY="your_key"
```

---

## 🚀 Usage Examples

### Start Telegram Bot with AI Agent

```bash
# Full integration (polling + agent)
kira telegram start --token $TELEGRAM_BOT_TOKEN --verbose

# Output:
# 🤖 Запуск Telegram бота с AI агентом...
#    Зарегистрировано инструментов: 5
#    ✅ AI Agent инициализирован
#    ✅ Agent подключен к Telegram через Event Bus
# ✅ Telegram бот с AI агентом запущен
#    Режим: long polling + event-driven agent
```

### Interact via Telegram

**User:** "Создай задачу: Написать отчёт по итогам спринта"

**Agent Response:**
```
✅ Шаг 1: task_create
   ID: task-20251008-1234, Заголовок: Написать отчёт по итогам спринта
```

---

## 🔧 Implementation Details

### MessageHandler

**Purpose:** Bridge between adapters and agent

```python
# Event flow
event = Event(
    name="message.received",
    payload={
        "message": "Create a task",
        "source": "telegram",
        "chat_id": 123456,
        "trace_id": "telegram-123456"
    }
)

# MessageHandler:
1. Receives event from EventBus
2. Calls AgentExecutor.chat_and_execute()
3. Formats response
4. Sends back via callback: adapter.send_message()
```

### Response Formatting

**Multi-step execution:**
```
✅ Шаг 1: task_create
   ID: task-1, Заголовок: Task 1
✅ Шаг 2: task_create
   ID: task-2, Заголовок: Task 2
❌ Шаг 3: Failed to create task 3
```

### Trace IDs

- **Auto-generated:** `{source}-{chat_id}` (e.g., `telegram-123456`)
- **Continuity:** Same chat_id = same conversation context
- **Memory:** Agent remembers previous exchanges per trace_id

---

## 📊 Agent Capabilities

When you message the bot, the AI agent has access to:

### 1. System Prompt
- Role: Kira's AI executor
- Workflow: Plan → Dry-Run → Execute → Verify
- Safety rules: Always dry-run before actions

### 2. Tools (Dynamically Injected)
- `task_create` - Create new tasks
- `task_update` - Update task status, assignee
- `task_get` - Get task details
- `task_list` - List tasks with filters
- `rollup_daily` - Generate daily summary

### 3. RAG Context (Optional)
- Vault README files
- Tool documentation
- Entity schemas

### 4. Conversation Memory
- Last 10 exchanges per chat
- Contextual understanding
- Multi-turn dialogues

---

## 🎯 Key Decisions

### Why Event-Driven for Polling?

**Benefits:**
1. **Decoupling** - Adapter doesn't know about Agent
2. **Multiple subscribers** - InboxPlugin + Agent can both listen
3. **Testability** - Easy to mock EventBus
4. **Extensibility** - Add more handlers without changing adapter

### Why Direct Call for Webhook?

**Benefits:**
1. **Simplicity** - Single HTTP handler
2. **Performance** - No event bus overhead
3. **Synchronous** - Telegram expects immediate response

---

## 🛠️ Future Improvements

### Phase 7 Enhancements

- [ ] **Confirmation workflows** - Button callbacks for destructive actions
- [ ] **Daily briefings** - Scheduled summaries
- [ ] **File handling** - Process photos and documents
- [ ] **Inline commands** - `/task list`, `/today`, etc.
- [ ] **Multi-user support** - Team chats

### Performance Optimizations

- [ ] **Async message handling** - Non-blocking responses
- [ ] **Message queue** - For high-volume chats
- [ ] **Caching** - LLM response caching for common queries

---

## 📚 Related Documentation

- [Agent Architecture](../src/kira/agent/README.md)
- [Telegram Adapter](../src/kira/adapters/telegram/README.md)
- [Event Bus](../src/kira/core/README.md)
- [Plugin SDK](../src/kira/plugin_sdk/README.md)

---

**Status:** ✅ Production-Ready
**Version:** 1.0.0
**Last Updated:** 2025-10-08
