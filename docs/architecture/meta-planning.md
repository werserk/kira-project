# 🎯 Meta-Planning: Adaptive Execution Strategies

**Дата**: 2025-10-10
**Статус**: ✅ **РЕАЛИЗОВАНО**

---

## 📋 Концепция

**Meta-Planning** - это когда LLM **САМ выбирает** стратегию выполнения задачи:
- Когда делать single-step
- Когда планировать заранее
- Когда параллелить
- Когда последовательно
- Когда адаптироваться по ходу

**Ключевая идея**: LLM = оркестратор, который динамически комбинирует подходы.

---

## 🎨 Доступные стратегии

### 1. Single-Step (простые задачи)
```
User: "Show my tasks"
↓
LLM: "Это просто, сделаю один шаг"
→ task_list()
→ Complete
```

**Когда использовать**:
- Простые запросы без зависимостей
- Read-only операции
- Не требует дополнительной информации

### 2. Sequential Exploration (нужна инфо)
```
User: "Delete task X"
↓
LLM: "Не знаю UID, сначала узнаю"
Step 1: task_list()
[observe results]
↓
LLM: "Теперь знаю UID, удалю"
Step 2: task_delete(uid="real-uid")
```

**Когда использовать**:
- Нужны данные для следующего шага
- Delete/update без UID
- Зависимые операции

### 3. Parallel Batch (независимые операции)
```
User: "Delete all tasks about X"
↓
LLM: "Сначала узнаю какие есть"
Step 1: task_list()
[observe results]
↓
LLM: "Нашел 10 задач, удалю все сразу"
Step 2: [task_delete(1), task_delete(2), ..., task_delete(10)] PARALLEL
```

**Когда использовать**:
- Массовые независимые операции
- Можно выполнить одновременно
- Нет зависимостей между операциями

### 4. Adaptive (обработка ошибок)
```
User: "Update task X"
↓
LLM: "Проверю существует ли"
Step 1: task_list()
[observe - found]
↓
LLM: "Есть, обновлю"
Step 2: task_update(uid="real-uid")
[observe - success]
→ Complete

// Альтернатива при ошибке:
[observe - error]
↓
LLM: "Ошибка, попробую по-другому"
Step 3: Try alternative approach
```

**Когда использовать**:
- Неуверенность в результате
- Возможны ошибки
- Нужна адаптация по ходу

### 5. Hybrid (комбинация)
```
User: "Create 3 tasks and mark first as done"
↓
LLM: "Создам параллельно, потом обновлю"
Step 1: [create("Task 1"), create("Task 2"), create("Task 3")] PARALLEL
[observe - got UIDs]
↓
LLM: "Создал, теперь обновлю первую"
Step 2: task_update(uid="task-1-uid", status="done")
```

**Когда использовать**:
- Сложные составные задачи
- Часть независима, часть зависима
- Оптимизация производительности

### 6. Exploratory (неопределенность)
```
User: "Do something with tasks about X"
↓
LLM: "Не знаю что конкретно, сначала посмотрю"
Step 1: task_list()
[observe - found 5 tasks]
↓
LLM: "Нашел 5 задач, пользователь наверное хочет..."
Step 2: Choose action based on context
```

**Когда использовать**:
- Неясный запрос
- Нужен контекст для решения
- Исследовательская задача

---

## 🔄 Как это работает

### Dynamic Replanning Loop

```
┌─────────────────────────────────────┐
│ User Request                         │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ LLM Planning (Meta-decision):       │
│ - Analyze request                   │
│ - Choose strategy                   │
│ - Return tool call(s)               │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ Execute Tool(s)                     │
│ - Single or multiple                │
│ - Parallel or sequential            │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ LLM Replanning (Adaptive):          │
│ - Observe results                   │
│ - Decide: continue/complete/replan  │
│ - Choose next strategy              │
└─────────────┬───────────────────────┘
              ↓
        Loop or Complete
```

**Ключевые моменты**:
1. **LLM вызывается после КАЖДОГО execution**
2. **LLM видит результаты предыдущих шагов**
3. **LLM САМ решает продолжать или завершить**
4. **LLM может менять стратегию по ходу**

---

## 💡 Примеры комбинирования

### Пример 1: Smart Delete
```
User: "Удали все старые задачи"

LLM думает: "Нужно узнать какие есть → фильтр по дате → batch delete"

Step 1 (Exploration):
  → task_list()

[observe: found 20 tasks, 15 old]

Step 2 (Parallel Batch):
  → [task_delete(uid1), task_delete(uid2), ..., task_delete(uid15)] PARALLEL

Complete!
```

### Пример 2: Robust Update
```
User: "Обнови задачу X как done"

LLM думает: "Проверю сначала → потом обновлю"

Step 1 (Sequential - verify):
  → task_list()

[observe: task X exists with uid="task-123"]

Step 2 (Execute):
  → task_update(uid="task-123", status="done")

[observe: success]

Complete!
```

### Пример 3: Error Recovery
```
User: "Создай задачу с дедлайном завтра"

LLM думает: "Попробую создать"

Step 1:
  → task_create(title="...", due_ts="2025-10-11")

[observe: ValidationError - invalid date format]

LLM думает: "Ошибка формата, попробую другой"

Step 2 (Adaptive):
  → task_create(title="...", due_ts="2025-10-11T00:00:00Z")

[observe: success]

Complete!
```

### Пример 4: Complex Workflow
```
User: "Создай 5 задач по проекту X и отметь 2 первые как in progress"

LLM думает: "Сначала создам все, потом обновлю нужные"

Step 1 (Parallel Creation):
  → [create("X-1"), create("X-2"), create("X-3"), create("X-4"), create("X-5")] PARALLEL

[observe: created with UIDs]

Step 2 (Parallel Update):
  → [update(uid1, status="doing"), update(uid2, status="doing")] PARALLEL

Complete!
```

---

## 🎓 Преимущества Meta-Planning

### 1. Адаптивность
- ✅ LLM подстраивается под задачу
- ✅ Нет жесткой схемы "сначала plan, потом execute"
- ✅ Оптимизация под конкретный случай

### 2. Эффективность
- ✅ Простые задачи → 1 шаг
- ✅ Сложные задачи → минимум шагов
- ✅ Автоматическая оптимизация

### 3. Надежность
- ✅ Адаптация к ошибкам
- ✅ Проверка перед действием
- ✅ Восстановление при сбое

### 4. Flexibility
- ✅ Комбинирование подходов
- ✅ Изменение стратегии по ходу
- ✅ Исследовательские задачи

---

## 📊 Сравнение подходов

| Подход | Простые задачи | Сложные задачи | Ошибки | Оптимизация |
|--------|---------------|---------------|---------|-------------|
| **Static Planning** | Оверкилл | ✅ Хорошо | ❌ Плохо | ❌ Нет |
| **Pure ReAct** | ✅ Хорошо | ⚠️ Медленно | ✅ Хорошо | ❌ Нет |
| **Meta-Planning** | ✅ Отлично | ✅ Отлично | ✅ Отлично | ✅ Да |

**Static Planning** (всегда full plan):
- ➕ Предсказуемо
- ➖ Оверкилл для простых задач
- ➖ Не адаптируется к ошибкам

**Pure ReAct** (всегда 1 step):
- ➕ Адаптивно
- ➖ Много LLM calls для сложных задач
- ➖ Не использует параллелизм

**Meta-Planning** (LLM выбирает):
- ➕ Адаптивно
- ➕ Эффективно
- ➕ Оптимально под задачу
- ➕ Использует все паттерны

---

## 🔧 Реализация в Kira

### Промпт для plan_node

```python
🎯 META-PLANNING - You choose the strategy:
You have FULL CONTROL over how to execute tasks. You can mix and match approaches:

1. Single-step (simple tasks): Call 1 tool → observe → decide next
2. Multi-step parallel (independent): Call MULTIPLE tools at once
3. Sequential chain (dependent): Tool → observe → tool → observe
4. Adaptive (learn as you go): Start → adjust based on results

STRATEGY EXAMPLES:
- Simple: task_list() → complete
- Exploration: task_list() → [decide] → task_delete()
- Batch: task_list() → [delete(1), delete(2), ..., delete(10)] PARALLEL
- Hybrid: [create(1), create(2)] PARALLEL → update(1)
```

**Ключевые особенности**:
- ✅ Явно указаны все стратегии
- ✅ Примеры комбинирования
- ✅ LLM сам выбирает
- ✅ Может менять стратегию по ходу

### LangGraph уже поддерживает

Инфраструктура уже готова:
- ✅ Dynamic replanning (plan после каждого execution)
- ✅ Parallel execution (multiple tool calls)
- ✅ Result observation (tool_results в state)
- ✅ Budget control (max_steps, tokens)

**Нужно было только**: обновить промпт! 🎉

---

## 📈 Метрики

### Что отслеживать

1. **Strategy distribution**
   - Сколько % single-step
   - Сколько % parallel
   - Сколько % sequential
   - Сколько % hybrid

2. **Efficiency metrics**
   - Среднее количество LLM calls на задачу
   - Время выполнения по типу задачи
   - Соотношение steps vs task complexity

3. **Adaptability metrics**
   - Сколько раз LLM меняет стратегию
   - Success rate после адаптации
   - Recovery rate от ошибок

---

## 🚀 Дальнейшие улучшения

### Short-term

1. **Logging стратегий**
   - Логировать какую стратегию выбрал LLM
   - Анализировать паттерны
   - Оптимизировать промпт

2. **Метрики эффективности**
   - Сравнивать подходы
   - A/B тесты
   - Оптимизация

### Medium-term

3. **Explicit strategy hints**
   - Дать LLM возможность явно указать стратегию
   - Например: `{strategy: "parallel_batch", tools: [...]}`
   - Лучше наблюдаемость

4. **Learning from failures**
   - Сохранять неудачные стратегии
   - Учить LLM на ошибках
   - Few-shot examples

### Long-term

5. **Multi-agent collaboration**
   - Один agent планирует
   - Другой выполняет
   - Третий проверяет

6. **Strategy optimization**
   - ML модель для выбора стратегии
   - Предсказание эффективности
   - Автоматическая оптимизация

---

## 💡 Философия

**Старый подход**: Жесткая схема (plan → execute → verify)
- Предсказуемо, но неэффективно
- Не адаптируется

**Meta-Planning**: LLM = интеллектуальный оркестратор
- Адаптивно под задачу
- Оптимально по умолчанию
- Естественно как человек думает

**Аналогия**:
- ❌ Робот: "Сначала план, потом выполнение, никаких отклонений"
- ✅ Человек: "Посмотрю что есть, решу что делать, адаптируюсь по ходу"

---

## ✅ Summary

**Meta-Planning** дает LLM полный контроль над процессом:
- ✅ Выбор стратегии под задачу
- ✅ Комбинирование подходов
- ✅ Адаптация по ходу
- ✅ Оптимизация автоматически

**Результат**: Умный ассистент, который ведет себя естественно и эффективно.

---

**Автор**: AI Assistant
**Дата**: 2025-10-10
**Версия**: 1.0
**Статус**: ✅ **АКТИВНО**

