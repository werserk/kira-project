# Best Practices: Предотвращение "галлюцинаций" в AI-агентах

## Проблема

LLM могут "галлюцинировать" - выдумывать данные, которых нет в реальности:
- Менять названия инструментов (`task_delete` → `task_remove`)
- Сообщать об успехе, когда была ошибка
- Добавлять несуществующие данные в ответы
- Искажать факты "для красоты" ответа

## Причины

1. **Конфликтующие инструкции** в промпте:
   ```
   ❌ "Не упоминай технические детали"
   → LLM думает: "Надо переписать tool_name"
   ```

2. **Недостаточная явность** статуса выполнения:
   ```
   ❌ Status: error
   → LLM может проигнорировать
   ```

3. **Приоритет стиля над точностью**:
   ```
   ❌ "Будь дружелюбной и позитивной"
   → LLM скрывает ошибки, чтобы "не расстраивать"
   ```

## Решения

### 1. Явные инструкции о честности

```python
# ❌ ПЛОХО
"- Не упоминай технические детали"

# ✅ ХОРОШО
"🚨 КРИТИЧЕСКИ ВАЖНО - ЧЕСТНОСТЬ И ТОЧНОСТЬ:
- НИКОГДА не выдумывай результаты выполнения!
- Если инструмент вернул ошибку - скажи об этом честно
- Если операция НЕ выполнена - не говори, что выполнена
- НЕ придумывай данные, которых нет в EXECUTION RESULTS
- Лучше сказать 'не получилось', чем солгать об успехе"
```

### 2. Визуальное выделение статуса

```python
# ❌ ПЛОХО
context_parts.append(f"Tool: {tool_name}, Status: {status}")

# ✅ ХОРОШО
status_emoji = "✅" if status == "ok" else "❌"
context_parts.append(f"{status_emoji} Tool: {tool_name}")
context_parts.append(f"   Status: {status.upper()}")

if status == "error":
    context_parts.append(f"   ⚠️ ERROR: {error}")
    context_parts.append(f"   ⚠️ IMPORTANT: This operation FAILED!")
```

### 3. Разделение фактов и презентации

```python
# Факты (структурированные данные)
execution_context = {
    "tool": "task_delete",
    "status": "error",
    "error": "Task not found"
}

# Презентация (для пользователя)
# LLM получает факты и превращает в естественный язык
# НО не может менять факты!
```

### 4. Валидация ответа агента

```python
def validate_response(response: str, execution_results: list) -> bool:
    """Проверяет, что ответ не содержит галлюцинаций."""

    # 1. Проверка упоминания несуществующих инструментов
    valid_tools = {"task_create", "task_delete", "task_list", ...}
    mentioned_tools = extract_tool_mentions(response)

    for tool in mentioned_tools:
        if tool not in valid_tools:
            logger.warning(f"Hallucinated tool mentioned: {tool}")
            return False

    # 2. Проверка соответствия статусов
    if any(r["status"] == "error" for r in execution_results):
        # Ответ НЕ должен содержать фразы успеха
        success_phrases = ["успешно", "готово", "выполнено", "сделано"]
        if any(phrase in response.lower() for phrase in success_phrases):
            logger.warning("Response claims success but tools failed")
            return False

    return True
```

### 5. Constrained Generation (Ограниченная генерация)

```python
# Использование JSON Schema для ответа
response_schema = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "data": {"type": "object"}
    },
    "required": ["success", "message"]
}

# LLM должен вернуть JSON, соответствующий схеме
# Это предотвращает "творческие" интерпретации
```

### 6. Grounding через RAG

```python
# Retrieval-Augmented Generation
# 1. Извлекаем релевантные факты из базы знаний
relevant_facts = rag_store.search(user_query)

# 2. Добавляем в контекст
context = f"""
ФАКТЫ (используй ТОЛЬКО эту информацию):
{relevant_facts}

ПРАВИЛО: Если информации нет в ФАКТАХ выше - скажи "Не знаю"
"""
```

### 7. Chain of Thought с проверкой

```python
# Попросить LLM объяснить свои рассуждения
prompt = """
1. Проанализируй EXECUTION RESULTS
2. Определи: успех или ошибка?
3. Сформулируй ответ пользователю
4. ПРОВЕРЬ: соответствует ли твой ответ результатам?

Формат:
{
  "analysis": "...",
  "is_success": true/false,
  "response": "...",
  "verified": true/false
}
"""
```

### 8. Few-shot примеры с акцентом на честность

```python
system_prompt = """
ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ:

Пример 1 (ошибка):
RESULTS: ❌ Tool: task_delete, Status: ERROR, Error: Task not found
ОТВЕТ: "Хм, не нашла такую задачу. Может, она уже удалена? Давай проверим список задач?"

Пример 2 (успех):
RESULTS: ✅ Tool: task_delete, Status: OK
ОТВЕТ: "Готово, задача удалена! Чем еще помочь?"

Пример 3 (частичный успех):
RESULTS:
  ✅ Tool: task_list, Status: OK
  ❌ Tool: task_delete, Status: ERROR
ОТВЕТ: "Я нашла задачи, но не смогла удалить. Похоже, нужно уточнить ID задачи."
"""
```

## Архитектурные паттерны

### Паттерн 1: Executor-Presenter

```
[User Input] → [Executor] → [Facts] → [Presenter] → [Natural Response]
                    ↓                        ↓
             Real tool calls         No tool calls,
             Real results            Only formatting
```

### Паттерн 2: Два промпта

```python
# Промпт 1: Исполнение (точность)
executor_prompt = """
Ты - точный исполнитель. Вызывай инструменты, возвращай факты.
НИКАКИХ интерпретаций!
"""

# Промпт 2: Презентация (дружелюбность)
presenter_prompt = """
Ты - дружелюбный помощник. Преврати ФАКТЫ в естественный ответ.
НО НИКОГДА не меняй факты!
"""
```

### Паттерн 3: Валидационный слой

```
[LLM Response] → [Validator] → [Approved/Rejected]
                       ↓
                 Checks:
                 - Tool names valid?
                 - Status matches facts?
                 - No hallucinated data?
```

## Метрики для мониторинга

```python
class HallucinationMetrics:
    def track(self, response: str, execution_results: list):
        # 1. Точность упоминания инструментов
        self.tool_name_accuracy = ...

        # 2. Соответствие статуса
        self.status_match_rate = ...

        # 3. Факт-чекинг данных
        self.data_accuracy = ...

        # 4. Ложные позитивы (говорит "успех" при ошибке)
        self.false_positive_rate = ...
```

## Тестирование

```python
def test_no_hallucination_on_error():
    """Агент не должен говорить об успехе при ошибке."""

    # Имитируем ошибку
    execution_results = [
        {"tool": "task_delete", "status": "error", "error": "Not found"}
    ]

    response = agent.generate_response(execution_results)

    # Проверяем
    assert "успешно" not in response.lower()
    assert "готово" not in response.lower()
    assert any(word in response.lower() for word in ["ошибка", "не получилось", "не нашла"])
```

## Рекомендации для Kira

### ✅ Что мы внедрили:

1. **Явные инструкции о честности** в промпте
2. **Визуальное выделение ошибок** (❌, ⚠️)
3. **Явное предупреждение** при ошибках инструментов

### 🔄 Что можно добавить:

1. **Валидацию ответов** перед отправкой пользователю
2. **Структурированный вывод** (JSON Schema)
3. **Метрики галлюцинаций** для мониторинга
4. **A/B тесты** разных промптов

### 📊 Как измерять успех:

```python
# Метрика 1: Точность статуса
accuracy = (correct_status_reports / total_operations) * 100

# Метрика 2: Ложные позитивы
false_positives = failed_ops_reported_as_success / total_failed_ops

# Цель: false_positives < 1%
```

## Источники и ссылки

- [Anthropic: Constitutional AI](https://arxiv.org/abs/2212.08073)
- [OpenAI: GPT Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
- [Google: Grounding LLMs](https://cloud.google.com/blog/products/ai-machine-learning/grounding-llms)
- [LangChain: Output Parsers](https://python.langchain.com/docs/modules/model_io/output_parsers/)

## Заключение

**Главный принцип**: Разделяй "что произошло" (факты) и "как это сказать" (стиль).

LLM должна:
- ✅ Быть точной в фактах
- ✅ Быть дружелюбной в стиле
- ❌ НЕ жертвовать точностью ради дружелюбности!

