# ✅ Тестирование исправления памяти

## Что было исправлено

**Проблема:** Кира говорила "я не вижу твой предыдущий вопрос", хотя память работала.

**Причина:** LangGraph nodes (`plan_node`, `respond_node`) передавали в LLM только последнее сообщение, игнорируя историю из `state.messages`.

**Исправление:** Теперь nodes передают ВСЮ историю разговора в LLM.

---

## 🚀 Как протестировать

### Шаг 1: ПЕРЕЗАПУСТИТЬ БОТА (ОБЯЗАТЕЛЬНО!)

```bash
# Остановить текущий процесс
pkill -9 -f "kira telegram"

# Запустить заново
kira telegram start --verbose
```

**Или через Docker:**
```bash
docker-compose down
docker-compose up --build
```

### Шаг 2: Проверить логи на наличие исправлений

```bash
tail -f logs/telegram_bot.log | grep "🔍 DEBUG"
```

**Должны увидеть:**
```
INFO     🔍 DEBUG: Calling LLM for planning with 3 messages (1 system + 2 conversation)
INFO     🔍 DEBUG: Calling LLM for response with 4 messages (system + 2 conversation + context)
```

### Шаг 3: Тест 1 - Простая проверка памяти

```
Вы: Привет! Меня зовут Максим
```

**Ожидается:** Кира ответит дружелюбно

```
Вы: Как меня зовут?
```

**Ожидается:**
```
Кира: Тебя зовут Максим!
```

✅ **Если Кира называет имя - память работает!**

### Шаг 4: Тест 2 - Вопрос о предыдущем вопросе

```
Вы: Какие у меня есть задачи?
```

**Ожидается:** Кира покажет список задач

```
Вы: Что я спросил в предыдущем вопросе?
```

**Ожидается:**
```
Кира: В предыдущем вопросе ты спросил "Какие у меня есть задачи?"
```

✅ **Если Кира цитирует предыдущий вопрос - исправление работает!**

❌ **Если говорит "не вижу предыдущий вопрос" - бот НЕ перезапущен!**

### Шаг 5: Тест 3 - Длинный диалог

```
Вы: Какая сегодня дата?
Кира: Сегодня 10 октября 2025 года
```

```
Вы: Создай задачу "Купить молоко"
Кира: Отлично, создала задачу!
```

```
Вы: О чем я спрашивал вначале нашего разговора?
```

**Ожидается:**
```
Кира: Вначале нашего разговора ты спрашивал о дате - какое сегодня число.
```

✅ **Если Кира помнит начало - память работает идеально!**

---

## 📊 Проверка логов

### Логи планирования

```bash
grep "Calling LLM for planning" logs/telegram_bot.log | tail -5
```

**До исправления:**
```
Calling LLM for planning with 2 messages (1 system + 1 conversation)
                                             ↑ ТОЛЬКО последнее!
```

**После исправления:**
```
Calling LLM for planning with 5 messages (1 system + 4 conversation)
                                             ↑ ВСЯ история!
```

### Логи генерации ответа

```bash
grep "Calling LLM for response" logs/telegram_bot.log | tail -5
```

**До исправления:**
```
Calling LLM for response with 2 messages (system + 1 conversation + context)
```

**После исправления:**
```
Calling LLM for response with 5 messages (system + 4 conversation + context)
```

---

## 🔍 Диагностика проблем

### Проблема 1: Бот все еще не помнит

**Симптом:** Кира говорит "не вижу предыдущий вопрос"

**Решение:**
```bash
# 1. Убедитесь, что процесс остановлен
ps aux | grep "kira telegram"
# Если что-то есть - убить:
pkill -9 -f "kira telegram"

# 2. Очистить кэш Python (опционально)
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null

# 3. Запустить заново
kira telegram start --verbose
```

### Проблема 2: Нет debug логов с "Calling LLM for..."

**Симптом:** В логах нет строк `🔍 DEBUG: Calling LLM for...`

**Решение:** Старый код все еще используется

```bash
# Проверить, что файл обновлен
grep "Calling LLM for planning" src/kira/agent/nodes.py

# Если не находит - файл не сохранен
# Перезапустить с force rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### Проблема 3: База данных пустая

```bash
# Проверить содержимое
sqlite3 artifacts/conversations.db "SELECT COUNT(*) FROM conversations;"

# Если 0 - память не сохраняется
# Проверить права
chmod 755 artifacts/
chmod 666 artifacts/conversations.db
```

---

## ✅ Критерии успеха

После исправления:

- [ ] Логи показывают `Calling LLM for planning with N messages` где N > 2
- [ ] Логи показывают `Calling LLM for response with N messages` где N > 2
- [ ] Кира может назвать ваше имя при повторном вопросе
- [ ] Кира может процитировать предыдущий вопрос
- [ ] Кира помнит начало диалога даже после 5+ сообщений
- [ ] После перезапуска бота история сохраняется (из БД)

---

## 🎯 Пример успешного диалога

```
[10:00] Вы: Привет! Меня зовут Максим
[10:00] Кира: Привет, Максим! Рада познакомиться. Чем могу помочь?

[10:01] Вы: Какие у меня есть задачи?
[10:01] Кира: У тебя сейчас 16 активных задач! Хочешь, я расскажу подробнее?

[10:02] Вы: Как меня зовут?
[10:02] Кира: Тебя зовут Максим! 😊  ← ✅ ПОМНИТ ИМЯ

[10:03] Вы: Что я спросил в предыдущем вопросе?
[10:03] Кира: В предыдущем вопросе ты спросил "Как меня зовут?" ← ✅ ПОМНИТ ВОПРОС

[10:04] Вы: А о чем я спрашивал самым первым?
[10:04] Кира: Самым первым ты поздоровался и представился - сказал, что тебя зовут Максим ← ✅ ПОМНИТ НАЧАЛО
```

**Если диалог выглядит так - ВСЁ РАБОТАЕТ ИДЕАЛЬНО! 🎉**

---

## 📝 Что изменилось в коде

### До (неправильно):

```python
# plan_node
messages = [
    Message(role="system", content=system_prompt),
    Message(role="user", content=last_user_message),  # ← Только последний!
]
```

### После (правильно):

```python
# plan_node
messages = [Message(role="system", content=system_prompt)]
for msg in state.messages:  # ← ВСЯ история!
    messages.append(Message(role=msg["role"], content=msg["content"]))
```

То же самое для `respond_node`.

---

## 🆘 Если ничего не помогло

Соберите диагностику и создайте issue:

```bash
# Соберите информацию
echo "=== MEMORY FIX DIAGNOSTIC ===" > memory-fix-debug.txt

echo "\n1. Latest logs with LLM calls:" >> memory-fix-debug.txt
grep -A 2 "Calling LLM" logs/telegram_bot.log | tail -20 >> memory-fix-debug.txt

echo "\n2. Database content:" >> memory-fix-debug.txt
sqlite3 artifacts/conversations.db "SELECT * FROM conversations LIMIT 5;" >> memory-fix-debug.txt

echo "\n3. nodes.py checksum:" >> memory-fix-debug.txt
md5sum src/kira/agent/nodes.py >> memory-fix-debug.txt

echo "\n4. Process info:" >> memory-fix-debug.txt
ps aux | grep kira >> memory-fix-debug.txt

cat memory-fix-debug.txt
```

---

**TL;DR:**

1. ✅ Перезапустить бота (`pkill -9 -f "kira telegram" && kira telegram start --verbose`)
2. ✅ Проверить логи (должны быть `Calling LLM for ... with N messages`)
3. ✅ Тест: "Как меня зовут?" после представления
4. ✅ Тест: "Что я спросил в предыдущем вопросе?"

**Если оба теста проходят - память работает! 🎉**

