# ⚡ Параллельное выполнение инструментов (Parallel Tool Execution)

**Дата**: 2025-10-10
**Автор**: AI Assistant
**Статус**: ✅ **РЕАЛИЗОВАНО**

---

## 📋 Проблема

**Симптом**: Кира удаляет задачи по одной, даже когда пользователь просит удалить несколько сразу.

**Пример**:
```
Пользователь: "Удали все задачи про X"
Кира находит 3 задачи, но:
  - Удаляет 1-ю задачу
  - Повторное планирование
  - Удаляет 2-ю задачу
  - Повторное планирование
  - Удаляет 3-ю задачу
```

**Результат**: 3 LLM вызова вместо 1! Медленно и дорого.

---

## 🔍 Причина

### Анализ логов

```
2025-10-10 18:30:04,027 - INFO - LLM requested 1 tool call(s)  ← Только 1!
2025-10-10 18:30:04,034 - INFO - Planning phase started (replanning)
2025-10-10 18:30:08,489 - INFO - LLM requested 1 tool call(s)  ← Снова 1!
2025-10-10 18:30:08,491 - INFO - Planning phase started (replanning)
2025-10-10 18:30:12,558 - INFO - LLM requested 1 tool call(s)  ← И опять 1!
```

LLM **ВСЕГДА** возвращал только 1 tool call, хотя:
- ✅ Claude 3.5 Sonnet **поддерживает** multiple tool calls
- ✅ Код **обрабатывает** массив `response.tool_calls`
- ✅ `tool_node` **выполняет** все инструменты из плана

### Корень проблемы

**Промпт показывал ТОЛЬКО последовательное выполнение**:

```python
# СТАРЫЙ промпт
EXAMPLE WORKFLOW (Delete task):
1. First, call task_list to find task UIDs
2. Then, call task_delete with the actual UID from results  ← ПО ОДНОМУ!
3. When done, don't call any more tools
```

LLM обучается на примерах → делает так же → удаляет по одному!

---

## ✅ Решение

### Обновлённый промпт

Добавлен **явный раздел о параллельном выполнении** с примерами:

```python
⚡ PARALLEL EXECUTION:
- When you need to perform MULTIPLE INDEPENDENT operations, call ALL tools at once
- For example: deleting 3 tasks → call task_delete 3 times in ONE response
- For example: creating 2 tasks → call task_create 2 times in ONE response
- Only use sequential calls when operations DEPEND on each other

IMPORTANT RULES:
- ALWAYS prefer parallel execution when operations are independent!

EXAMPLES:

Example 1 - Delete multiple tasks (PARALLEL):
User: "Delete all tasks about project X"
After task_list returns UIDs: [task-123, task-456, task-789]
→ Call task_delete(uid="task-123"), task_delete(uid="task-456"), task_delete(uid="task-789") ALL AT ONCE

Example 2 - Create multiple tasks (PARALLEL):
User: "Create tasks: buy milk, walk dog, send email"
→ Call task_create(title="buy milk"), task_create(title="walk dog"), task_create(title="send email") ALL AT ONCE

Example 3 - Sequential (when dependent):
User: "Create a task and mark it as done"
Step 1: Call task_create(title="...")
Step 2 (after creation): Call task_update(uid=<from_step1>, status="done")
```

---

## 📊 Ожидаемый эффект

### До исправления

**Запрос**: "Удали 3 задачи"

```
1. LLM planning → task_delete(task-1)    [3 секунды]
2. Execute → delete task-1
3. LLM replanning → task_delete(task-2)  [3 секунды]
4. Execute → delete task-2
5. LLM replanning → task_delete(task-3)  [3 секунды]
6. Execute → delete task-3
7. LLM replanning → complete

Итого: 4 LLM вызова, ~12 секунд
```

### После исправления

**Запрос**: "Удали 3 задачи"

```
1. LLM planning → [task_delete(task-1), task_delete(task-2), task_delete(task-3)]  [3 секунды]
2. Execute → delete all 3 tasks in parallel
3. LLM replanning → complete  [3 секунды]

Итого: 2 LLM вызова, ~6 секунд
```

**Улучшение**:
- ⚡ **Скорость**: 2x быстрее (6s вместо 12s)
- 💰 **Стоимость**: 2x дешевле (2 вызова вместо 4)
- 📈 **Эффективность**: Меньше нагрузка на API

---

## 🔧 Технические детали

### Как работает multiple tool calls

#### 1. LLM возвращает массив

```python
response = llm_adapter.tool_call(messages, tools)

# response.tool_calls = [
#     ToolCall(name="task_delete", arguments={"uid": "task-123"}),
#     ToolCall(name="task_delete", arguments={"uid": "task-456"}),
#     ToolCall(name="task_delete", arguments={"uid": "task-789"}),
# ]
```

#### 2. plan_node обрабатывает все

```python
tool_calls = []
for call in response.tool_calls:
    tool_calls.append({
        "tool": call.name,
        "args": call.arguments,
        "dry_run": False
    })

# tool_calls = [
#     {"tool": "task_delete", "args": {"uid": "task-123"}, ...},
#     {"tool": "task_delete", "args": {"uid": "task-456"}, ...},
#     {"tool": "task_delete", "args": {"uid": "task-789"}, ...},
# ]
```

#### 3. tool_node выполняет последовательно

```python
# src/kira/agent/nodes.py - tool_node()
for step in state.plan:
    tool_name = step.get("tool")
    args = step.get("args", {})

    tool = tool_registry.get(tool_name)
    result = tool.execute(args)

    state.tool_results.append(result)
```

**Важно**: Выполнение **последовательно** в рамках одного цикла планирования, но **все за один раз** без повторного вызова LLM!

---

## 🎯 Когда использовать параллельное выполнение

### ✅ ПАРАЛЛЕЛЬНО (один LLM вызов)

**Независимые операции**:
- ✅ Удалить несколько задач
- ✅ Создать несколько задач
- ✅ Обновить несколько разных задач
- ✅ Получить информацию о нескольких объектах

**Пример**:
```
User: "Удали задачи про проект X"
→ task_list() → [task-1, task-2, task-3]
→ [task_delete(task-1), task_delete(task-2), task_delete(task-3)] ✅
```

### 🔄 ПОСЛЕДОВАТЕЛЬНО (несколько LLM вызовов)

**Зависимые операции**:
- 🔄 Создать задачу, затем получить её ID, затем обновить
- 🔄 Найти задачи, затем решить что с ними делать
- 🔄 Выполнить действие, проверить результат, продолжить

**Пример**:
```
User: "Создай задачу и сразу отметь её как выполненную"
Step 1: task_create(title="X") → {uid: "task-123"}
Step 2: task_update(uid="task-123", status="done")  ← Нужен UID из Step 1!
```

---

## 📈 Метрики для мониторинга

### Что отслеживать

1. **Среднее количество tool calls на запрос**
   - До: ~1.2
   - После: ожидаем ~2-3 (для batch операций)

2. **Среднее время выполнения batch операций**
   - До: N * 3 секунды (N = количество задач)
   - После: 6 секунд (независимо от N)

3. **Количество LLM вызовов на запрос**
   - До: 2-4 для batch операций
   - После: 2 (планирование + завершение)

---

## 🧪 Как протестировать

### Тест 1: Удаление нескольких задач

```bash
# Создать тестовые задачи
poetry run kira telegram --session test
> "Создай задачи: test1, test2, test3"

# Удалить все сразу
> "Удали все задачи про test"
```

**Ожидаемое поведение**:
```
[Planning] LLM requested 1 tool call(s)  ← task_list
[Executing] task_list → [task-1, task-2, task-3]
[Planning] LLM requested 3 tool call(s)  ← ✅ ВСЕ СРАЗУ!
[Executing] task_delete(task-1)
[Executing] task_delete(task-2)
[Executing] task_delete(task-3)
[Planning] LLM requested 0 tool call(s)  ← complete
```

### Тест 2: Создание нескольких задач

```bash
> "Создай задачи: купить молоко, погулять с собакой, отправить письмо"
```

**Ожидаемое поведение**:
```
[Planning] LLM requested 3 tool call(s)  ← ✅ ВСЕ СРАЗУ!
[Executing] task_create(title="купить молоко")
[Executing] task_create(title="погулять с собакой")
[Executing] task_create(title="отправить письмо")
[Planning] LLM requested 0 tool call(s)  ← complete
```

---

## 💡 Lessons Learned

### Что работает

1. ✅ **Explicit is better than implicit**: Нужно ЯВНО говорить LLM что делать
2. ✅ **Examples are powerful**: LLM учится на примерах
3. ✅ **Test with real scenarios**: Важно проверять на реальных use cases

### Что НЕ работает

1. ❌ Неявные инструкции ("call one or more tools") - слишком расплывчато
2. ❌ Примеры только последовательного выполнения - LLM копирует паттерн
3. ❌ Надежда что "LLM сам поймёт" - не поймёт без примеров

---

## 🚀 Следующие шаги

### Сейчас (Done ✅)

- [x] Добавлен раздел о параллельном выполнении
- [x] Добавлены примеры parallel execution
- [x] Явно указано "ALWAYS prefer parallel"

### Дальше (Рекомендуется)

1. **Протестировать** на реальных запросах
   - Удаление 3+ задач
   - Создание 3+ задач
   - Batch обновления

2. **Собрать метрики**
   - Сколько tool calls в среднем
   - Время выполнения batch операций
   - Количество LLM вызовов

3. **Оптимизировать дальше**
   - Рассмотреть true parallel execution (asyncio)
   - Batch API для некоторых провайдеров
   - Кэширование повторяющихся запросов

---

## 📚 References

### Anthropic Tool Use Documentation

- [Multiple Tool Calls](https://docs.anthropic.com/claude/docs/tool-use#multiple-tool-calls)
- [Best Practices](https://docs.anthropic.com/claude/docs/tool-use#best-practices)

### Internal Docs

- [Native Function Calling Migration](./014-native-function-calling-migration.md)
- [LangGraph Integration](../architecture/langgraph-llm-integration.md)

---

## ✅ Checklist

- [x] Проблема диагностирована
- [x] Корневая причина найдена
- [x] Промпт обновлён
- [x] Добавлены примеры parallel execution
- [x] Документация создана
- [ ] **Протестировано на реальных запросах**
- [ ] **Метрики собраны**

---

**Статус**: ✅ **ГОТОВО К ТЕСТИРОВАНИЮ**

**Ожидаемый эффект**:
- 2x быстрее для batch операций
- 2x дешевле (меньше LLM вызовов)
- Лучший UX (мгновенное выполнение)

---

**Автор**: AI Assistant
**Дата**: 2025-10-10
**Версия**: 1.0

