# Как включить LangGraph в Telegram боте

## TL;DR - Быстрый старт

```bash
# 1. Установите зависимости (если еще не установлены)
poetry install --extras agent

# 2. Включите LangGraph в .env
echo "KIRA_EXECUTOR_TYPE=langgraph" >> .env

# 3. Перезапустите бота
# Готово! Теперь Telegram использует LangGraph с Phase 1-3
```

## Что получите

### ДО (Legacy Executor)
```
Пользователь: "Создай задачу"
    ↓
AgentExecutor:
  1. Plan (LLM генерирует план)
  2. Execute (выполняет tools)
  3. Готово
```

**Проблемы:**
- ❌ Нет проверки безопасности
- ❌ Нет верификации результатов
- ❌ Нет retry при ошибках
- ❌ Нет детального аудита
- ❌ Нет circuit breaker
- ❌ Простая цепочка без рефлексии

### ПОСЛЕ (LangGraph Executor)
```
Пользователь: "Создай задачу"
    ↓
LangGraphExecutor:
  1. Plan (LLM генерирует план)
  2. Reflect (Проверка безопасности плана) ✨
  3. Tool (Выполнение с retry/circuit breaker) ✨
  4. Verify (Проверка результатов) ✨
  5. (возможен loop если нужна корректировка)
  6. Готово
```

**Преимущества:**
- ✅ Safety review перед выполнением
- ✅ Verification после выполнения
- ✅ Retry с exponential backoff
- ✅ Circuit breaker при повторных ошибках
- ✅ Детальный JSONL audit trail
- ✅ Prometheus metrics
- ✅ Multi-provider LLM с fallback
- ✅ State persistence для recovery
- ✅ Policy enforcement
- ✅ Цепочка рассуждений и действий

## Детальная конфигурация

### 1. Минимальная конфигурация (.env)

```bash
# Просто включить LangGraph
KIRA_EXECUTOR_TYPE=langgraph

# API ключи (хотя бы один)
ANTHROPIC_API_KEY=sk-ant-...
# или
OPENAI_API_KEY=sk-...
# или включить Ollama fallback
KIRA_ENABLE_OLLAMA_FALLBACK=true
```

### 2. Полная конфигурация (.env)

```bash
# ============================================================================
# LangGraph Executor
# ============================================================================

KIRA_EXECUTOR_TYPE=langgraph

# LangGraph nodes (все по умолчанию true)
KIRA_LANGGRAPH_REFLECTION=true      # Reflect node (safety review)
KIRA_LANGGRAPH_VERIFICATION=true    # Verify node (result validation)
KIRA_LANGGRAPH_MAX_STEPS=10         # Max steps (budget control)

# ============================================================================
# LLM Providers (хотя бы один)
# ============================================================================

# Anthropic (лучше для planning/reasoning)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_DEFAULT_MODEL=claude-3-5-sonnet-20241022

# OpenAI (лучше для JSON structuring)
OPENAI_API_KEY=sk-...
OPENAI_DEFAULT_MODEL=gpt-4-turbo-preview

# OpenRouter (100+ models, хороший fallback)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_DEFAULT_MODEL=anthropic/claude-3.5-sonnet

# Ollama (локально, бесплатно)
KIRA_ENABLE_OLLAMA_FALLBACK=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3

# ============================================================================
# LLM Routing (какой провайдер для каких задач)
# ============================================================================

KIRA_PLANNING_PROVIDER=anthropic    # Plan/Reflect nodes → Claude
KIRA_STRUCTURING_PROVIDER=openai    # Tool execution → GPT-4
KIRA_DEFAULT_PROVIDER=openrouter    # Fallback
```

### 3. Для разработки (без API ключей)

```bash
# Используем только Ollama (локально, бесплатно)
KIRA_EXECUTOR_TYPE=langgraph
KIRA_ENABLE_OLLAMA_FALLBACK=true

# API ключи НЕ нужны! Все через Ollama
```

**Требуется:**
```bash
# Установить Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Запустить
ollama serve

# Скачать модель
ollama pull llama3
```

## Проверка работы

### 1. Запустить бота с LangGraph

```bash
# Убедитесь что KIRA_EXECUTOR_TYPE=langgraph в .env
poetry run kira-telegram
```

### 2. Отправить сообщение в Telegram

```
Вы: Создай задачу "Протестировать LangGraph"

Кира:
✅ Создана задача: Протестировать LangGraph
📋 ID: task-xxx
```

### 3. Проверить audit log

```bash
# LangGraph пишет детальный audit trail
cat artifacts/audit/agent/agent-$(date +%Y-%m-%d).jsonl | jq
```

Вы увидите:
```json
{
  "trace_id": "...",
  "node": "plan",
  "timestamp": "...",
  "input": {"message": "Создай задачу..."},
  "output": {"plan": [...]},
  "elapsed_ms": 150
}
{
  "trace_id": "...",
  "node": "reflect",
  "output": {"safe": true, "reasoning": "Plan is safe"},
  "elapsed_ms": 85
}
{
  "trace_id": "...",
  "node": "tool",
  "output": {"status": "ok", "data": {"uid": "task-xxx"}},
  "elapsed_ms": 120
}
...
```

### 4. Проверить metrics

```bash
# Если используете FastAPI service
curl http://localhost:8000/metrics
```

## Что изменилось в поведении?

### Более детальные ответы

**Legacy:**
```
✅ Готово
```

**LangGraph:**
```
✅ Создана задача: Протестировать LangGraph
📋 ID: task-123
⏱️ Время: 0.5s
🔍 Проверено: FSM transitions, no duplicates
```

### Больше безопасности

**Legacy:**
```
Вы: Удали все задачи
Кира: ❌ Ошибка: Tool not found: task_delete_all
```

**LangGraph:**
```
Вы: Удали все задачи
Кира: ⚠️ Действие отклонено: Destructive operation requires confirmation
      Используйте: "Удали задачу task-123 (подтверждаю)"
```

### Автоматическое исправление ошибок

**Legacy:**
```
Вы: Измени статус на "завершено"
Кира: ❌ Ошибка: Invalid FSM transition: todo -> завершено
```

**LangGraph:**
```
Вы: Измени статус на "завершено"
Кира: [Reflect node] Обнаружена ошибка: неправильный статус
      [Planning node] Пересоздание плана: статус "done"
      ✅ Статус изменен на "done"
```

### Retry при сбоях LLM

**Legacy:**
```
Вы: Создай задачу
Кира: ❌ Ошибка: LLM timeout
```

**LangGraph:**
```
Вы: Создай задачу
[Internal] LLM timeout → retry → fallback to Ollama
Кира: ✅ Создана задача
```

## Откат на Legacy (если что-то не так)

Просто измените в `.env`:

```bash
# Было:
KIRA_EXECUTOR_TYPE=langgraph

# Стало:
KIRA_EXECUTOR_TYPE=legacy
```

Перезапустите бота - всё вернется к старому поведению.

## Мониторинг

### Логи

```bash
# LangGraph логи
tail -f artifacts/audit/agent/agent-$(date +%Y-%m-%d).jsonl

# Telegram логи
tail -f logs/adapters/telegram.jsonl
```

### Метрики

```python
from kira.agent import create_metrics_collector

metrics = create_metrics_collector()
health = metrics.get_health()

print(f"Status: {health.status}")  # healthy/degraded/unhealthy
print(f"Steps: {metrics.steps_total}")
print(f"Failures: {metrics.failures_total}")
```

### Audit Trail Reconstruction

```python
from kira.agent import create_audit_logger

audit = create_audit_logger()
path = audit.reconstruct_path("trace-id-xxx")

for event in path:
    print(f"{event['node']}: {event['elapsed_ms']}ms")
```

## FAQ

**Q: Нужно ли менять промпты?**
A: Нет! LangGraph использует те же prompts, просто добавляет больше nodes в workflow.

**Q: Будет ли работать без LangGraph dependencies?**
A: Да! Если `langgraph` не установлен, автоматически fallback на legacy executor.

**Q: Влияет ли на скорость ответа?**
A: Добавляется ~200-500ms на reflect/verify nodes, но зато больше безопасности и точности.

**Q: Можно ли отключить reflect или verify?**
A: Да:
```bash
KIRA_LANGGRAPH_REFLECTION=false  # Отключить safety review
KIRA_LANGGRAPH_VERIFICATION=false  # Отключить result validation
```

**Q: Работает ли с существующим Telegram адаптером?**
A: Да! Полная backward compatibility. UnifiedExecutor прозрачно подменяет executor.

## Рекомендации

**Production:**
```bash
KIRA_EXECUTOR_TYPE=langgraph
KIRA_LANGGRAPH_REFLECTION=true    # Обязательно!
KIRA_LANGGRAPH_VERIFICATION=true  # Обязательно!
ANTHROPIC_API_KEY=...             # Claude для планирования
OPENAI_API_KEY=...                # GPT-4 для tools
KIRA_ENABLE_OLLAMA_FALLBACK=true  # Резерв
```

**Development:**
```bash
KIRA_EXECUTOR_TYPE=langgraph
KIRA_ENABLE_OLLAMA_FALLBACK=true  # Только Ollama
# (без API ключей - бесплатно!)
```

**Testing:**
```bash
KIRA_EXECUTOR_TYPE=legacy  # Быстрее для unit tests
```

## Что дальше?

После включения LangGraph вы получаете доступ к Phase 1-3 компонентам:

- ✅ Policies (capability enforcement)
- ✅ Retry policies (circuit breaker)
- ✅ Audit trail (JSONL events)
- ✅ Metrics (Prometheus)
- ✅ State persistence (resume after crash)
- ✅ Context memory (multi-turn conversations)
- ✅ RAG integration (documentation-enhanced planning)

Читайте: `docs/architecture/langgraph-llm-integration.md`

