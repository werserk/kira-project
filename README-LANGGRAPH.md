# LangGraph - Core Architecture

**LangGraph является основой всех NL взаимодействий в Kira.**

## Философия

🎯 **Любое взаимодействие на естественном языке ДОЛЖНО проходить через LangGraph.**

Почему?
1. **Надежность**: Plan → Reflect → Execute → Verify обеспечивает качество
2. **Безопасность**: Reflect node проверяет безопасность до выполнения
3. **Наблюдаемость**: Полный audit trail для каждого действия
4. **Отказоустойчивость**: Retry, circuit breaker, fallback встроены
5. **Качество**: Verification node проверяет результаты

## Архитектура

```
User Input (NL)
      ↓
┌─────────────────────────────────────────────┐
│           LangGraph State Machine           │
│                                             │
│  Plan → Reflect → Tool → Verify → Done     │
│    ↓       ↓        ↓       ↓              │
│  Claude   Claude   Tools   Tools           │
│  (reason) (safety) (exec)  (check)         │
│                                             │
│  Budget Guards: steps, tokens, time        │
│  Error Handling: retry, circuit breaker   │
│  Observability: audit, metrics, traces    │
└─────────────────────────────────────────────┘
      ↓
User Response
```

## По умолчанию включено

LangGraph **включен по умолчанию** во всех компонентах:

- ✅ Telegram bot
- ✅ HTTP API (`/agent/chat`)
- ✅ CLI commands
- ✅ Message handlers
- ✅ Any NL interface

**Нет необходимости** что-либо включать или конфигурировать.

## Минимальная конфигурация

Для работы нужен хотя бы один LLM provider:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
# или
OPENAI_API_KEY=sk-...
# или
KIRA_ENABLE_OLLAMA_FALLBACK=true  # Бесплатный локальный
```

Всё! LangGraph работает автоматически.

## Ключевые преимущества

### 1. Цепочка рассуждений

```
Пользователь: "Создай задачу на завтра с приоритетом high"

LangGraph:
  [Plan] Анализирую запрос... → Нужно создать задачу
  [Reflect] Проверяю безопасность... → Безопасно
  [Tool] Вызываю task_create... → Успех
  [Verify] Проверяю результат... → Задача создана корректно
  
Ответ: ✅ Создана задача ID: task-123, Due: tomorrow, Priority: high
```

### 2. Самоисправление

```
Пользователь: "Измени статус на завершено"

LangGraph:
  [Plan] Нужен task_update с status="завершено"
  [Reflect] ОШИБКА: неверный статус (должно быть "done")
  [Plan] Пересоздаю план с status="done"
  [Tool] task_update(status="done") → Успех
  
Ответ: ✅ Статус изменен на "done"
```

### 3. Отказоустойчивость

```
[Tool] LLM timeout при вызове Anthropic
[Retry] Повторная попытка через 1s
[Retry] Повторная попытка через 2s
[Fallback] Переход на OpenAI
[Success] Запрос выполнен через OpenAI
```

### 4. Полная наблюдаемость

Каждый запрос создает audit trail:

```json
{"trace_id": "...", "node": "plan", "elapsed_ms": 150, "status": "ok"}
{"trace_id": "...", "node": "reflect", "elapsed_ms": 85, "status": "ok"}
{"trace_id": "...", "node": "tool", "elapsed_ms": 120, "status": "ok"}
{"trace_id": "...", "node": "verify", "elapsed_ms": 45, "status": "ok"}
```

Вы **всегда** можете восстановить полный путь выполнения.

## Компоненты

### Phase 1: Foundations
- ✅ State Machine (LangGraph)
- ✅ Nodes (plan, reflect, tool, verify, route)
- ✅ LLM Adapter Bridge (multi-provider)

### Phase 2: Enrichment
- ✅ Tool Registry (JSON schemas)
- ✅ Context Memory (multi-turn)
- ✅ RAG Integration (docs)
- ✅ State Persistence (recovery)

### Phase 3: Production
- ✅ Policy Enforcement (capabilities)
- ✅ Retry Policies (circuit breaker)
- ✅ Audit Trail (JSONL)
- ✅ Metrics (Prometheus)

## Конфигурация

### Рекомендуемая (Production)

```bash
# .env

# LLM Providers (multi-provider = надежность)
ANTHROPIC_API_KEY=sk-ant-...         # Primary: Claude для reasoning
OPENAI_API_KEY=sk-...                # Secondary: GPT-4 для JSON
KIRA_ENABLE_OLLAMA_FALLBACK=true     # Fallback: Ollama локально

# LangGraph (все дефолтные значения оптимальны)
KIRA_LANGGRAPH_REFLECTION=true       # Safety review
KIRA_LANGGRAPH_VERIFICATION=true     # Result validation
KIRA_LANGGRAPH_MAX_STEPS=10          # Budget control
```

### Для разработки (без API ключей)

```bash
# .env

# Только Ollama (бесплатно)
KIRA_ENABLE_OLLAMA_FALLBACK=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3

# Всё! LangGraph работает с Ollama
```

## Мониторинг

### Логи

```bash
# Audit trail
tail -f artifacts/audit/agent/agent-$(date +%Y-%m-%d).jsonl

# Structured logs
tail -f logs/core/agent.jsonl
```

### Метрики

```bash
# Health check
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8000/metrics
```

### Трассировка

```python
from kira.agent import create_audit_logger

audit = create_audit_logger()
trace = audit.reconstruct_path("trace-id-xxx")

for event in trace:
    print(f"{event['node']}: {event['elapsed_ms']}ms")
```

## Legacy Executor (deprecated)

**Не используйте** legacy executor в production.

Он оставлен только для:
- Backward compatibility
- Debugging специфичных проблем
- Unit tests (где нужна изоляция)

В любых реальных NL взаимодействиях используйте LangGraph.

## FAQ

**Q: Обязателен ли LangGraph?**
A: Да. Для всех NL взаимодействий это основа. Legacy executor deprecated.

**Q: Влияет ли на скорость?**
A: +200-500ms на reflect/verify, но вы получаете надежность и безопасность.

**Q: Можно ли отключить reflect или verify?**
A: Технически да, но **не рекомендуется**. Это снижает качество и безопасность.

**Q: Нужны ли API ключи?**
A: Хотя бы один provider нужен. Можно использовать Ollama (бесплатно).

**Q: Работает ли с существующими адаптерами?**
A: Да! Telegram, CLI, HTTP API - все используют LangGraph автоматически.

## См. также

- [Детальная документация](docs/HOW-TO-ENABLE-LANGGRAPH.md)
- [Архитектура LLM интеграции](docs/architecture/langgraph-llm-integration.md)
- [Примеры](examples/langgraph_integration_example.py)
- [Phase 1-3 план](CONTRIBUTING.md)

---

**💡 Главное:**

LangGraph - это не "фича", это **архитектурная основа** Kira.  
Все NL взаимодействия проходят через него. Всегда. По умолчанию.

