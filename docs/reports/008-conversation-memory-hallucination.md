# Report 008: Галлюцинации на основе истории разговора

**Дата**: 2025-10-10
**Trace ID**: `ad7d1a16-7dad-4fee-a22c-ed30de974aab`
**Статус**: 🔄 Частично исправлено

## Проблема

Пользователь спросил: "Какие у меня есть актуальные задачи?"

**Реальность** (vault/tasks/): 17 файлов задач
**Ответ Kira**: "У тебя сейчас всего 2 активные задачи"

### Откуда Kira взяла "2 задачи"?

**ИЗ ИСТОРИИ РАЗГОВОРА!** Не из vault!

## Диагностика

### Путь выполнения:

```
1. User: "Какие у меня есть актуальные задачи?"
2. Loading 20 messages from memory
3. Planning phase → LLM для генерации плана
4. ❌ ERROR: Failed to parse plan JSON: Expecting value: line 1 column 1 (char 0)
5. → Routing → "respond" (новое поведение после исправления)
6. Response generation БЕЗ ВЫЗОВА task_list
7. LLM видит:
   - EXECUTION RESULTS: (пусто!)
   - История: "У тебя сейчас 16 активных задач" (старый ответ)
   - История: разговор об удалении задач
8. LLM "обновляет" информацию: "У тебя сейчас 2 задачи"
```

### Ключевые факты:

```python
# Лог
"Failed to parse plan JSON: Expecting value: line 1 column 1 (char 0)"
→ Это значит LLM вернул ПУСТОЙ ответ или невалидный JSON

# НИ ОДИН инструмент НЕ выполнился!
"Tool task_list" - НЕ НАЙДЕНО в логах

# HTTP ответ от LLM
Content-Length: 412 bytes  # Очень маленький ответ!
```

### История разговора (20 сообщений!):

```
History[0]: user - "Какие у меня есть актуальные задачи"
History[1]: assistant - "У тебя сейчас 16 активных задач:"  ← СТАРАЯ ИНФОРМАЦИЯ
History[2]: user - "Удали задачу My first task"
History[3]: assistant - "Извини, но я не смогла удалить..."
...
History[20]: user - "Какие у меня есть актуальные задачи?" ← НОВЫЙ ЗАПРОС
```

## Корневые причины

### 1. LLM вернул невалидный JSON при планировании

**Возможные причины:**
- Слишком большой контекст (20 сообщений + system prompt)
- Token limit достигнут
- LLM "запутался" в истории
- Проблема с промптом

### 2. respond_node не проверяет наличие tool_results

**Код (до исправления):**
```python
def respond_node(state: AgentState, llm_adapter: LLMAdapter):
    context_parts = []

    if state.tool_results:  # Есть результаты
        # Используем их

    if state.error:  # Есть ошибка
        # Добавляем в контекст

    # Но если НЕТ ни результатов, ни ошибки?
    # → LLM использует историю разговора!
```

### 3. История разговора используется как "источник правды"

LLM в `respond_node` получает:
```
Messages:
1. System prompt: "Будь дружелюбной и честной"
2. История (20 сообщений): "У тебя 16 задач... Удали My first task..."
3. Context: EXECUTION RESULTS: (пусто!)

LLM думает: "Раз нет новых данных, обновлю старые.
Было 16 задач, удаляли несколько → сейчас ~2 задачи"
```

### 4. Слишком большая история (20 сообщений)

- Занимает много tokens
- Может привести к превышению context window
- Увеличивает latency
- Снижает качество генерации плана

## Решение

### 1. ✅ Детекция отсутствия tool_results

```python
# CRITICAL: Check if we have ANY tool results
if not state.tool_results and not state.error:
    logger.warning(f"NO TOOL RESULTS and NO ERROR - possible hallucination!")
    state.error = "Не удалось выполнить операцию (ошибка планирования)"
```

### 2. ✅ Явное предупреждение LLM

```python
if state.error and not state.tool_results:
    context_parts.append("\n❌ NO TOOLS WERE EXECUTED!")
    context_parts.append("❌ DO NOT use conversation history - you have NO REAL DATA!")
    context_parts.append("❌ Tell user honestly that you couldn't get the information!")
```

### 3. 🔄 TODO: Ограничение истории разговора

```python
# Вместо 20 сообщений - брать только последние N
MAX_HISTORY_MESSAGES = 6  # 3 пары user-assistant

# Или использовать summarization для старых сообщений
if len(messages) > MAX_HISTORY_MESSAGES:
    old_messages = messages[:-MAX_HISTORY_MESSAGES]
    summary = summarize_messages(old_messages)
    messages = [summary] + messages[-MAX_HISTORY_MESSAGES:]
```

### 4. 🔄 TODO: Улучшение обработки ошибок планирования

```python
# Если LLM вернул невалидный JSON
except json.JSONDecodeError as e:
    # Попытка #2: упрощенный промпт без истории
    if retry_count < 1:
        logger.info("Retrying with simplified prompt...")
        simplified_prompt = get_simplified_planning_prompt()
        return plan_with_prompt(simplified_prompt, user_request)
    else:
        # Честная ошибка
        return {
            "error": "Не могу спланировать выполнение",
            "plan": [],
            "status": "error"
        }
```

### 5. 🔄 TODO: Fallback к прямому вызову инструмента

```python
# Если планирование провалилось, но запрос простой
if "какие задачи" in user_request.lower():
    # Прямой вызов без планирования
    return direct_tool_call("task_list", {})
```

## Ожидаемое поведение после исправления

### Сценарий: Ошибка планирования

```
User: "Какие у меня задачи?"

Kira (внутри):
1. Planning → ❌ ERROR (invalid JSON)
2. state.error = "Не удалось выполнить операцию"
3. Routing → "respond"
4. respond_node:
   - Проверка: tool_results? НЕТ
   - Проверка: error? ДА
   - Context: "❌ NO TOOLS EXECUTED! DO NOT use conversation history!"

Kira (пользователю):
"Извини, что-то пошло не так при выполнении задачи.
Техническая ошибка: Не удалось выполнить операцию (ошибка планирования)"
```

## Метрики

### До исправления

- **Hallucination on Empty Results**: 100% (всегда использует историю)
- **User Confusion**: Высокая (ответ не соответствует реальности)

### После исправления (ожидается)

- **Hallucination on Empty Results**: 0% (явная ошибка вместо выдумки)
- **User Trust**: Восстановлено (честность важнее "красивого" ответа)

## Дополнительные рекомендации

### 1. Мониторинг планирования

```python
# Отслеживать частоту ошибок планирования
planning_errors_per_hour = ...

if planning_errors_per_hour > THRESHOLD:
    alert("High planning failure rate! Check LLM provider or prompts")
```

### 2. A/B тестирование размера истории

```
Группа A: max_history=20
Группа B: max_history=6

Метрики:
- Planning success rate
- Response quality
- Latency
```

### 3. Кэширование частых запросов

```python
# "Какие задачи?" - частый запрос
# Можно кэшировать результат task_list на 1-2 минуты
if is_frequent_query(user_request):
    cached_result = get_cached_tool_result("task_list")
    if cached_result and not is_stale(cached_result):
        return cached_result
```

### 4. Упрощенный режим при ошибках

```python
# Если планирование провалилось - упростить
class SimpleExecutor:
    """Fallback executor без планирования."""

    def execute(self, user_request):
        # Прямое сопоставление: запрос → инструмент
        if "какие задачи" in request.lower():
            return self.call_tool("task_list", {})
        elif "создай задачу" in request.lower():
            return self.call_tool("task_create", extract_args(request))
        # ...
```

## Выводы

1. **История разговора - источник галлюцинаций** когда нет реальных данных
2. **Детекция пустых результатов критична** - лучше сказать "не знаю"
3. **Слишком большая история вредит** - нужно ограничение
4. **Fallback механизмы важны** - когда LLM "не справляется"
5. **Честность > Удобство** - лучше признать ошибку

## Следующие шаги

1. ✅ Детекция отсутствия tool_results
2. ✅ Явное предупреждение LLM
3. ⏳ Ограничение истории разговора (макс. 6-10 сообщений)
4. ⏳ Retry с упрощенным промптом
5. ⏳ Fallback к прямому вызову инструментов
6. ⏳ Мониторинг частоты ошибок планирования
7. ⏳ A/B тестирование размера истории

---

**Статус**: Частично исправлено. Теперь Kira скажет "не получилось" вместо выдумки.
**Требуется**: Ограничение истории разговора для предотвращения ошибок планирования.

