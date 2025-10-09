# LangGraph + LLM Multi-Provider Integration

## Обзор

LangGraph в Kira интегрирован с системой multi-provider LLM через `LangGraphLLMBridge`. Это обеспечивает:

✅ **Работу с любым LLM провайдером** (OpenAI, Anthropic, OpenRouter, Ollama)  
✅ **Автоматический fallback** на Ollama при сбоях  
✅ **Provider routing** (разные модели для разных задач)  
✅ **Retry логику** и обработку ошибок  

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Executor                        │
│  (Phase 1: State Machine, Nodes, Graph)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ uses
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              LangGraphLLMBridge                              │
│  (Integration Layer - llm_integration.py)                    │
│                                                              │
│  • Implements LLMAdapter interface                           │
│  • Wraps LLMRouter                                           │
│  • Maps task types                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ delegates to
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     LLMRouter                                │
│  (Phase 0: Multi-Provider Routing)                          │
│                                                              │
│  • Routes by task type (planning/structuring/default)        │
│  • Manages retry logic                                       │
│  • Handles fallback                                          │
└──────────────┬───────────────┬──────────────┬───────────────┘
               │               │              │
               ▼               ▼              ▼
    ┌─────────────┐ ┌────────────┐ ┌──────────────┐
    │  OpenAI     │ │ Anthropic  │ │  OpenRouter  │
    │  Adapter    │ │  Adapter   │ │   Adapter    │
    └─────────────┘ └────────────┘ └──────────────┘
                               │
                               │ fallback
                               ▼
                      ┌──────────────┐
                      │    Ollama    │
                      │   (local)    │
                      └──────────────┘
```

## Компоненты

### 1. LangGraphLLMBridge

**Файл**: `src/kira/agent/llm_integration.py`

**Роль**: Мост между LangGraph (который ожидает `LLMAdapter`) и `LLMRouter` (который управляет несколькими провайдерами).

**Методы**:
- `generate()` - генерация текста
- `chat()` - диалог
- `tool_call()` - вызовы функций

**Особенности**:
- Реализует интерфейс `LLMAdapter`
- Маппит task_type для LangGraph nodes
- Делегирует все вызовы в `LLMRouter`

### 2. LLMRouter (существующий)

**Файл**: `src/kira/adapters/llm/router.py`

**Роль**: Управление множественными LLM провайдерами.

**Функциональность**:
- Provider selection по типу задачи
- Retry с exponential backoff
- Fallback chain (primary → fallback → Ollama)
- Error handling и logging

### 3. Adapters (существующие)

**Файлы**: `src/kira/adapters/llm/*_adapter.py`

**Поддерживаемые провайдеры**:
- `OpenAIAdapter` - GPT-4, GPT-3.5
- `AnthropicAdapter` - Claude 3.5, Claude 3
- `OpenRouterAdapter` - 100+ моделей
- `OllamaAdapter` - локальные модели (Llama, Mistral, etc.)

## Использование

### Базовое использование

```python
from kira.agent import create_langgraph_llm_adapter, LangGraphExecutor

# Создаем multi-provider адаптер
llm = create_langgraph_llm_adapter(
    api_keys={
        "anthropic": "sk-ant-...",
        "openai": "sk-...",
    },
    planning_provider="anthropic",      # Claude для планирования
    structuring_provider="openai",      # GPT-4 для JSON
    enable_ollama_fallback=True,        # Fallback на Ollama
)

# LangGraph работает с любым провайдером!
executor = LangGraphExecutor(llm, tool_registry)
result = executor.execute("Create a task")
```

### Routing Strategy

```python
# Пример: разные модели для разных задач
llm = create_langgraph_llm_adapter(
    api_keys={"anthropic": "...", "openai": "..."},
    
    # Planning nodes → Claude (лучше для reasoning)
    planning_provider="anthropic",
    
    # JSON structuring → GPT-4 (лучше для structured output)
    structuring_provider="openai",
    
    # Default для остального
    default_provider="openrouter",
    
    # Всегда fallback на Ollama
    enable_ollama_fallback=True,
)
```

### Fallback Chain

При сбое провайдера автоматически происходит fallback:

1. **Primary Provider** (anthropic/openai/openrouter)
   - Попытка с retry (3 раза с exponential backoff)
   
2. **Fallback Provider** (если настроен)
   - Попытка с альтернативным провайдером
   
3. **Ollama (local)**
   - Финальный fallback на локальную модель
   - Всегда доступен если `enable_ollama_fallback=True`

### Пример: Только Ollama (без облачных провайдеров)

```python
# Для разработки или offline работы
llm = create_langgraph_llm_adapter(
    api_keys={},  # Нет API ключей
    enable_ollama_fallback=True,
)

# Работает с локальным Ollama!
# Требует: ollama serve + ollama pull llama3
```

## Task Type Mapping

LangGraph nodes маппятся на task types для оптимального routing:

| LangGraph Node | Task Type    | Recommended Provider | Reasoning                       |
|----------------|--------------|----------------------|---------------------------------|
| `plan_node`    | PLANNING     | Anthropic (Claude)   | Лучше для multi-step reasoning  |
| `reflect_node` | PLANNING     | Anthropic (Claude)   | Критическое мышление            |
| `tool_node`    | STRUCTURING  | OpenAI (GPT-4)       | Хорошо для JSON                 |
| `verify_node`  | DEFAULT      | Any                  | Простая задача                  |

## Конфигурация через Environment Variables

```bash
# .env файл
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...

# LangGraph автоматически использует эти ключи
```

```python
import os

llm = create_langgraph_llm_adapter(
    api_keys={
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
        "openrouter": os.getenv("OPENROUTER_API_KEY"),
    },
)
```

## Integration с Phase 1-3 компонентами

LLM интеграция работает со всеми Phase 1-3 компонентами:

```python
# Phase 1: LangGraph
from kira.agent import LangGraphExecutor, AgentState

# Phase 2: Tools, Memory, RAG, Persistence
from kira.agent import (
    create_tool_executor,
    create_context_memory,
    create_rag_integration,
    create_persistence,
)

# Phase 3: Safety, Observability
from kira.agent import (
    create_policy_enforcer,
    create_audit_logger,
    create_metrics_collector,
)

# LLM Integration (работает со всем!)
from kira.agent import create_langgraph_llm_adapter

# Полный стек
llm = create_langgraph_llm_adapter(...)
executor = LangGraphExecutor(llm, tool_registry)
```

## Error Handling

Bridge автоматически обрабатывает ошибки:

```python
from kira.adapters.llm import LLMError, LLMTimeoutError, LLMRateLimitError

try:
    result = executor.execute("Create task")
except LLMTimeoutError:
    # Timeout → автоматически retry → fallback
    pass
except LLMRateLimitError:
    # Rate limit → exponential backoff → fallback
    pass
except LLMError as e:
    # Любая другая ошибка LLM
    print(f"LLM failed: {e}")
```

## Преимущества

### 1. Гибкость провайдеров
- Переключение между провайдерами без изменения кода
- Тестирование с разными моделями
- Cost optimization (cheap models для простых задач)

### 2. Надежность
- Автоматический fallback при сбоях
- Retry логика с exponential backoff
- Локальный Ollama как последняя линия защиты

### 3. Производительность
- Routing по типу задачи (optimal model selection)
- Параллельные вызовы где возможно
- Token optimization

### 4. Developer Experience
- Единая конфигурация для всех провайдеров
- Consistent API независимо от провайдера
- Легкое тестирование (mock LLMRouter)

## Тестирование

```python
# Unit tests с mock LLMRouter
from unittest.mock import Mock

mock_router = Mock()
mock_router.chat.return_value = LLMResponse(content="{...}")

bridge = LangGraphLLMBridge(mock_router)
executor = LangGraphExecutor(bridge, tool_registry)

# E2E tests с реальными провайдерами
llm = create_langgraph_llm_adapter(
    api_keys={"anthropic": real_key},
    enable_ollama_fallback=False,  # Для контроля в тестах
)
```

## Best Practices

1. **Всегда используйте fallback в production**:
   ```python
   enable_ollama_fallback=True  # Always!
   ```

2. **Оптимизируйте routing по задачам**:
   ```python
   planning_provider="anthropic"    # Claude для сложного reasoning
   structuring_provider="openai"    # GPT-4 для JSON
   ```

3. **Мониторьте provider usage**:
   ```python
   metrics = create_metrics_collector()
   # Отслеживайте какой провайдер используется
   ```

4. **Graceful degradation**:
   ```python
   # Приоритет: cloud → fallback → local
   # Всегда должен быть хотя бы один working provider
   ```

## Troubleshooting

### "No API keys provided"
```python
# Solution: добавьте хотя бы один ключ или включите Ollama
llm = create_langgraph_llm_adapter(
    api_keys={"anthropic": "sk-..."},  # или
    enable_ollama_fallback=True,       # Ollama как fallback
)
```

### "Ollama connection refused"
```bash
# Solution: запустите Ollama
ollama serve

# И установите модель
ollama pull llama3
```

### "Rate limit exceeded"
```python
# Solution: используйте retry и fallback
# Уже встроено в LLMRouter!
# Автоматически перейдет на fallback provider
```

## См. также

- [LangGraph Integration Plan](../../CONTRIBUTING.md#langgraph-integration)
- [LLMRouter Documentation](./llm-router.md)
- [Phase 1-3 Architecture](./telegram-integration.md)
- [Examples](../../examples/langgraph_integration_example.py)

