# Dynamic Replanning Architecture

## Обзор

**Дата**: 2025-10-10
**Статус**: Реализовано

## Проблема

При выполнении многошаговых операций (например, удаление задачи) LLM генерировал весь план сразу, используя placeholder'ы типа `<specific_uid>` для параметров, которые должны были быть получены из результатов предыдущих шагов. Эти placeholder'ы никогда не заменялись на реальные значения, что приводило к ошибкам выполнения.

### Пример проблемного сценария:

```
Запрос: "Удали эту задачу"

План LLM (генерируется сразу):
1. task_list → получить список задач
2. task_get(uid='<specific_uid>') → ОШИБКА! '<specific_uid>' - это буквальная строка

Результат: task_get не может найти задачу с ID '<specific_uid>'
```

## Решение: Dynamic Replanning

Вместо генерации всего плана сразу, система теперь возвращается к LLM **после каждого успешного выполнения шага**, позволяя LLM:
- Видеть реальные результаты предыдущих шагов
- Принимать решения на основе актуальных данных
- Планировать следующие шаги с реальными значениями (UIDs, и т.д.)
- Обрабатывать условную логику и ошибки динамически

### Новый сценарий работы:

```
Запрос: "Удали эту задачу"

1-й цикл планирования:
   Plan: task_list()
   Execute: task_list → [{"uid": "task-123", "title": "Test"}]

2-й цикл планирования (LLM видит результаты):
   Plan: task_delete(uid="task-123")  # Реальный UID!
   Execute: task_delete("task-123") → success

3-й цикл планирования (LLM видит успех):
   Plan: [] (пустой план = задача выполнена)
   Route: → respond_step → генерация естественного ответа
```

## Изменения в коде

### 1. Граф выполнения (`src/kira/agent/graph.py`)

**Изменено:**
- `route_after_tool()`: теперь всегда возвращается к `plan_step` после успешного выполнения
- `route_after_verify()`: также возвращается к `plan_step`
- `route_after_plan()`: добавлена обработка статуса `completed` → `respond_step`

**До:**
```python
def route_after_tool(state):
    if state.current_step < len(state.plan):
        return "tool_step"  # Выполнить следующий шаг из плана
    return "respond_step"
```

**После:**
```python
def route_after_tool(state):
    # Всегда возвращаться к планированию
    return "plan_step"
```

### 2. Узел планирования (`src/kira/agent/nodes.py`)

**Изменено:**
- System prompt: добавлены инструкции о динамическом переплапнировании
- Добавление результатов предыдущих шагов в контекст LLM
- Обработка пустого плана как сигнала завершения

**Ключевые добавления:**

1. **Результаты предыдущих шагов в контекст:**
```python
if state.tool_results:
    results_summary = "PREVIOUS TOOL EXECUTIONS:\n"
    for result in state.tool_results:
        results_summary += f"{tool_name}: {status}\n"
        results_summary += f"Result: {json.dumps(data)}\n"
    messages.append(Message(role="assistant", content=results_summary))
```

2. **Обработка завершения:**
```python
if not tool_calls:  # Пустой план
    return {
        "plan": [],
        "status": "completed",  # → respond_step
    }
```

### 3. Обновленный промпт для LLM

```
🔄 DYNAMIC REPLANNING MODE:
- You will be called AFTER each tool execution to plan the next step(s)
- You can see the results of previous tool executions
- Use REAL data from previous results, NOT placeholders
- Plan one or more steps, based on what's needed
- If the task is COMPLETE, return an empty tool_calls array []

RULES:
- Use REAL data from previous results (uids, values, etc.)
- DO NOT use placeholders like '<uid_from_previous_step>' - use actual UIDs!

COMPLETION:
- If the user's request is fully satisfied, return: {"tool_calls": [], "reasoning": "Task completed"}
```

## Преимущества

✅ **Надежность**: LLM всегда работает с реальными данными
✅ **Гибкость**: Поддержка условной логики и обработки ошибок
✅ **Масштабируемость**: Работает для сложных многошаговых операций
✅ **Отладка**: Четкое логирование каждого цикла планирования

## Недостатки

⚠️ **Больше LLM вызовов**: Каждый шаг требует нового вызова LLM
⚠️ **Выше стоимость**: Больше токенов используется
⚠️ **Медленнее**: Увеличенная latency из-за дополнительных вызовов

## Примеры использования

### Пример 1: Удаление одной задачи

```
User: "Удали задачу 'Добавить Кире речь'"

Цикл 1:
  LLM Plan: [{"tool": "task_list", "args": {}}]
  Result: [{"uid": "task-456", "title": "Добавить Кире речь"}]

Цикл 2:
  LLM Plan: [{"tool": "task_delete", "args": {"uid": "task-456"}}]
  Result: {"success": true}

Цикл 3:
  LLM Plan: []
  → Переход к respond_step
```

### Пример 2: Удаление нескольких задач

```
User: "Удали все задачи со статусом 'done'"

Цикл 1:
  LLM Plan: [{"tool": "task_list", "args": {"status": "done"}}]
  Result: [{"uid": "task-1"}, {"uid": "task-2"}]

Цикл 2:
  LLM Plan: [
    {"tool": "task_delete", "args": {"uid": "task-1"}},
    {"tool": "task_delete", "args": {"uid": "task-2"}}
  ]
  Result: [{success}, {success}]

Цикл 3:
  LLM Plan: []
  → Переход к respond_step
```

## Тестирование

Для тестирования:
1. Создать задачу через Telegram: "Добавь задачу 'Тестовая задача'"
2. Попросить удалить: "Удали задачу 'Тестовая задача'"
3. Проверить логи на наличие циклов переплапнирования

## Совместимость

- ✅ Обратно совместимо: старые промпты продолжат работать
- ✅ Не ломает существующий функционал
- ✅ Reflection и Verification работают как прежде

## Дальнейшие улучшения

1. **Оптимизация LLM вызовов**: Кэширование контекста, использование более дешевых моделей для планирования
2. **Параллельное выполнение**: Выполнение независимых шагов параллельно
3. **Timeout механизм**: Ограничение количества циклов переплапнирования
4. **Метрики**: Мониторинг количества циклов и стоимости выполнения

