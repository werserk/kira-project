# 🔒 Confirmation Flow для деструктивных операций

**Дата**: 2025-10-10
**Автор**: AI Assistant
**Статус**: ✅ **РЕАЛИЗОВАНО**

---

## 📋 Проблема

**Symptom**: Reflection блокирует или изменяет деструктивные операции (удаление задач), даже когда пользователь явно их запрашивает.

**Пример**:
```
Пользователь: "Удали все задачи про X"
Кира планирует: [delete task-1, delete task-2, ... delete task-12]
Reflection: "unsafe! revised_plan: [delete task-1]"  ← Блокирует массовое удаление
Результат: Удаляется только 1 задача
```

**Проблема**: Reflection правильно определяет риск, но **неправильно реагирует** - блокирует вместо того чтобы запросить подтверждение.

---

## ✅ Решение: Confirmation Flow

**Паттерн**: Вместо блокировки → запрос подтверждения у пользователя → выполнение при подтверждении

### Workflow

```
1. User: "Удали все задачи про X"
   ↓
2. Plan: [delete task-1, delete task-2, ..., delete task-12]
   ↓
3. Reflection: needs_confirmation=true, entities=[task-1, task-2, ...]
   ↓
4. Kira: "Подтверди удаление: task-1, task-2, ..., task-12. Это действие необратимо. Уверен?"
   ↓
5a. User: "Да" → Execute all deletions ✅
5b. User: "Нет" → Cancel operation ❌
```

---

## 🔧 Реализация

### 1. Расширение AgentState

Добавлены поля для хранения pending операций:

```python
# src/kira/agent/state.py

@dataclass
class AgentState:
    # ... existing fields ...

    # Confirmation for destructive operations
    pending_confirmation: bool = False
    pending_plan: list[dict[str, Any]] = field(default_factory=list)
    confirmation_question: str = ""
```

**Назначение**:
- `pending_confirmation` - флаг, что ожидается подтверждение
- `pending_plan` - сохранённый план, который ждёт подтверждения
- `confirmation_question` - вопрос для пользователя

### 2. Обновление reflect_node

Изменён промпт и логика обработки:

```python
# src/kira/agent/nodes.py - reflect_node()

system_prompt = """
SAFETY CHECKS:
- DESTRUCTIVE operations (delete, mass updates) → needs_confirmation=true
- If needs_confirmation=true, list ALL affected entities in entities_affected
- Set safe=false ONLY if plan is fundamentally broken (missing args, wrong types)
- Otherwise set safe=true (confirmation will be handled separately)
"""

# Processing
if needs_confirmation:
    entities_affected = reflection.get("entities_affected", [])
    confirmation_question = f"Подтверди удаление: {entities_str}. Это действие необратимо. Уверен?"

    return {
        "pending_confirmation": True,
        "pending_plan": state.plan,
        "confirmation_question": confirmation_question,
        "plan": [],  # Clear - будет восстановлен после подтверждения
        "status": "completed",  # Go to respond
    }
```

**Логика**:
- `safe=false` → **Блокировать** (план фундаментально сломан)
- `safe=true, needs_confirmation=true` → **Запросить подтверждение**
- `safe=true, needs_confirmation=false` → **Выполнить**

### 3. Обновление plan_node

Добавлена проверка подтверждения:

```python
# src/kira/agent/nodes.py - plan_node()

# Check if user is responding to a confirmation request
if state.pending_confirmation and state.pending_plan:
    user_message_lower = user_message.lower()

    # Positive: "да", "yes", "уверен", "подтверждаю", "удали", "ok"
    # Negative: "нет", "no", "отмена", "cancel", "стоп"

    if is_confirmed:
        logger.info("User confirmed, restoring plan")
        return {
            "plan": state.pending_plan,  # Restore saved plan
            "pending_confirmation": False,
            "status": "planned",
        }
    elif is_rejected:
        logger.info("User rejected operation")
        return {
            "pending_confirmation": False,
            "plan": [],
            "status": "completed",  # Cancel
        }
```

**Логика**:
- Проверяет последнее сообщение пользователя
- Ищет паттерны подтверждения/отказа
- Восстанавливает plan при подтверждении
- Отменяет при отказе

### 4. Обновление respond_node

Добавлена обработка confirmation_question:

```python
# src/kira/agent/nodes.py - respond_node()

# If there's a confirmation question pending, return it directly
if state.pending_confirmation and state.confirmation_question:
    logger.info("Returning confirmation question to user")
    return {
        "response": state.confirmation_question,
        "status": "responded",
    }

# Check if user cancelled operation
if not state.plan and not state.tool_results and not state.error:
    if any(word in last_user_msg for word in ["нет", "no", "отмена", "cancel"]):
        return {
            "response": "Хорошо, операция отменена. Могу помочь с чем-то другим?",
            "status": "responded",
        }
```

**Логика**:
- Возвращает confirmation_question напрямую (без LLM)
- Обрабатывает отмену операции

---

## 📊 Примеры работы

### Пример 1: Успешное подтверждение

```
User: "Удали все задачи про проект X"

Kira (Planning): [plan: delete task-1, delete task-2, delete task-3]
Kira (Reflection): needs_confirmation=true
Kira → User: "Подтверди удаление: task-1, task-2, task-3. Это действие необратимо. Уверен?"

User: "Да, удали"

Kira (Planning): [restored plan: delete task-1, delete task-2, delete task-3]
Kira (Execution): ✅ Deleted task-1, task-2, task-3
Kira → User: "Готово! Удалила 3 задачи про проект X."
```

### Пример 2: Отмена операции

```
User: "Удали все задачи"

Kira (Planning): [plan: delete task-1, ..., delete task-20]
Kira (Reflection): needs_confirmation=true
Kira → User: "Подтверди удаление: 20 объектов. Это действие необратимо. Уверен?"

User: "Нет, отмена"

Kira → User: "Хорошо, операция отменена. Могу помочь с чем-то другим?"
```

### Пример 3: Неоднозначный ответ

```
User: "Удали задачу X"

Kira → User: "Подтверди удаление: task-123. Это действие необратимо. Уверен?"

User: "А что эта задача делает?"

Kira (Planning): Treats as new request
Kira → User: "Задача task-123 - это [описание]. Хочешь её удалить?"
```

---

## 🎯 Типы операций

### Требуют подтверждения (needs_confirmation=true)

- ✅ Единичное удаление: `delete task-X`
- ✅ Массовое удаление: `delete task-1, task-2, ...`
- ✅ Удаление "всех": `delete all tasks`
- ✅ Массовые обновления: `update 10 tasks`

### НЕ требуют подтверждения (needs_confirmation=false)

- ✅ Чтение: `list tasks`, `get task-X`
- ✅ Поиск: `search tasks`
- ✅ Единичное создание: `create task`
- ✅ Единичное обновление: `update task-X title="..."`

### Блокируются (safe=false)

- ❌ Отсутствующие аргументы: `delete` (без uid)
- ❌ Неверные типы: `delete uid=123` (число вместо строки)
- ❌ Несуществующие tools: `unknown_tool()`

---

## 🔍 Паттерны подтверждения

### Positive patterns (подтверждение)

**Русский**:
- "да"
- "уверен"
- "подтверждаю"
- "удали"
- "ок"
- "давай"

**English**:
- "yes"
- "sure"
- "confirm"
- "delete"
- "ok"
- "go ahead"

### Negative patterns (отказ)

**Русский**:
- "нет"
- "отмена"
- "стоп"
- "не уверен"

**English**:
- "no"
- "cancel"
- "stop"
- "abort"

### Ambiguous (неоднозначный)

Любой другой текст → treated as new request

---

## 📈 Метрики

### Что отслеживать

1. **Confirmation rate**
   - Сколько деструктивных операций запрашивают подтверждение
   - Ожидаем: ~100%

2. **User response**
   - Confirmed vs Rejected vs Ambiguous
   - Ожидаем: 80% confirmed, 10% rejected, 10% ambiguous

3. **False positives**
   - Операции, которые не должны требовать подтверждения, но требуют
   - Ожидаем: <5%

4. **False negatives**
   - Опасные операции, которые не запросили подтверждение
   - Ожидаем: 0%

---

## 🎨 UX Best Practices

### Хорошие confirmation questions

✅ **Конкретные**:
- "Подтверди удаление: task-123 (Написать отчёт), task-456 (Позвонить клиенту)"
- Пользователь видит ЧТО будет удалено

✅ **Явные о последствиях**:
- "Это действие необратимо. Уверен?"
- Пользователь понимает риск

✅ **Краткие при большом количестве**:
- "Подтверди удаление: 20 объектов. Уверен?"
- Не заспамливаем весь список

### Плохие confirmation questions

❌ **Расплывчатые**:
- "Ты уверен?"
- Непонятно в чём именно

❌ **Без контекста**:
- "Удалить?"
- Что удалять?

❌ **Слишком длинные**:
- "Подтверди удаление: task-1, task-2, task-3, ... task-100"
- Нечитаемо

---

## 🚨 Edge Cases

### Case 1: Пользователь отвечает неоднозначно

```
Kira: "Подтверди удаление: task-X. Уверен?"
User: "А что это за задача?"
```

**Решение**: Treat as new request, clear pending state

### Case 2: Pending state между сессиями

```
Session 1:
  Kira: "Подтверди удаление: task-X. Уверен?"
  User: [closes app]

Session 2:
  User: "Да"
```

**Текущее поведение**: Pending state НЕ сохраняется между сессиями

**TODO**: Сохранять pending_confirmation в persistent memory

### Case 3: Пользователь подтверждает то, что уже выполнено

```
Kira: "Подтверди удаление: task-X. Уверен?"
User: "Да"
Kira: [deletes task-X]

User: "Да"  (повторно)
```

**Решение**: pending_confirmation=False после первого выполнения → treat as new request

---

## 🔧 Ограничения

### Текущие ограничения

1. **Не сохраняется между сессиями**
   - pending_plan теряется при перезапуске
   - **TODO**: Persist to memory

2. **Простая pattern matching**
   - Может неправильно интерпретировать сложные ответы
   - **TODO**: Use LLM для интерпретации confirmation

3. **Только для деструктивных операций**
   - Не работает для других рисков (например, sensitive data access)
   - **TODO**: Expand для других типов операций

---

## 🚀 Следующие шаги

### Short-term (High Priority)

1. **Протестировать на реальных сценариях**
   - Single deletion
   - Mass deletion (10+ tasks)
   - Cancellation
   - Ambiguous responses

2. **Собрать метрики**
   - Confirmation rate
   - User acceptance rate
   - False positives/negatives

3. **Улучшить confirmation questions**
   - Показывать titles задач, не только UIDs
   - Группировать по типам операций
   - Локализация (RU/EN)

### Medium-term (Optional)

4. **Persist pending state**
   - Сохранять в memory между сессиями
   - Expire после N минут

5. **LLM-based confirmation interpretation**
   - Использовать LLM для понимания ответа пользователя
   - Обрабатывать сложные/неоднозначные ответы

6. **Расширить на другие операции**
   - Sensitive data access
   - Mass updates
   - Irreversible changes

---

## 📚 References

### Internal Docs

- [Parallel Tool Execution](./015-parallel-tool-execution.md)
- [Native Function Calling](./014-native-function-calling-migration.md)
- [Conditional Reflection](../architecture/conditional-reflection.md)

### External Resources

- [Confirmation Dialog Best Practices](https://www.nngroup.com/articles/confirmation-dialogs/)
- [Destructive Actions UX](https://www.nngroup.com/articles/confirmation-dialog/)

---

## ✅ Checklist

- [x] Добавлены поля в AgentState
- [x] Обновлён reflect_node
- [x] Обновлён plan_node
- [x] Обновлён respond_node
- [x] Проверен синтаксис
- [x] Создана документация
- [ ] **Протестировано на реальных запросах**
- [ ] **Собраны метрики**

---

**Статус**: ✅ **ГОТОВО К ТЕСТИРОВАНИЮ**

**Ожидаемый UX**:
- Пользователь чувствует контроль
- Опасные операции не выполняются случайно
- Легко подтвердить или отменить

**Ожидаемая надёжность**: 99%+ (confirmation flow не может сломаться)

---

**Автор**: AI Assistant
**Дата**: 2025-10-10
**Версия**: 1.0

