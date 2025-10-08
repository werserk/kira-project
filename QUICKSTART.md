# Kira Quick Start - 5 минут до первого запуска

**Самый быстрый способ начать использовать Kira**

---

## ⚡ Быстрый старт (без адаптеров)

### 1. Установка (1 минута)

```bash
# Клонировать (если ещё не сделали)
cd ~/Projects/kira-project

# Установить
poetry install

# Активировать
poetry shell
```

### 2. Проверка (10 секунд)

```bash
kira --help
```

### 3. Инициализация (10 секунд)

```bash
# Скопировать конфиг
cp config/kira.yaml.example kira.yaml

# Создать Vault
kira vault init
```

### 4. Первая задача (10 секунд)

```bash
kira vault new --type task --title "Изучить Kira"
```

### 5. Проверка (10 секунд)

```bash
# Список задач
ls vault/tasks/

# Посмотреть задачу
cat vault/tasks/task-*.md

# Валидация
kira validate
```

**🎉 Готово! Kira работает.**

---

## 📱 Добавить Telegram (опционально, +15 минут)

### 1. Создать бота

1. Найти **@BotFather** в Telegram
2. Отправить: `/newbot`
3. Задать имя и username
4. Скопировать токен

### 2. Настроить

```bash
# Создать .env
cp config/env.example .env

# Отредактировать
nano .env
```

Добавить:
```bash
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
TELEGRAM_CHAT_ID=ваш_chat_id  # Получить через @userinfobot
```

### 3. Установить зависимости

```bash
poetry install --extras telegram
```

### 4. Включить в config

```yaml
# В kira.yaml
plugins:
  enabled:
    - kira-inbox
    - kira-calendar
    - kira-deadlines

adapters:
  telegram:
    enabled: true
    mode: "bot"
  
  gcal:
    enabled: true
```

### 5. Тест

```bash
# Написать боту любое сообщение в Telegram
# Потом выполнить:
kira inbox --verbose
```

**✅ Telegram работает!**

---

## 📊 Базовые команды

```bash
# Создать entity
kira vault new --type task --title "Task"
kira vault new --type note --title "Note"

# Inbox processing
kira inbox

# Отчёты
kira rollup daily
kira rollup weekly

# Валидация
kira validate

# Статус
kira diag status

# Логи
kira diag tail --follow
```

---

## 📂 Структура Vault

После `kira vault init`:

```
vault/
├── inbox/        # Необработанные файлы
├── tasks/        # Задачи
├── notes/        # Заметки  
├── events/       # События
├── projects/     # Проекты
└── @Indexes/     # Отчёты и индексы
```

---

## 🎯 Типичный workflow

### Вариант 1: CLI

```bash
# 1. Создать задачу
kira vault new --type task --title "Buy groceries"

# 2. Редактировать в любом редакторе
nano vault/tasks/task-*.md

# 3. Изменить status: todo → doing

# 4. Валидация
kira validate

# 5. Отчёт
kira rollup daily
```

### Вариант 2: Telegram + CLI

```bash
# 1. Написать в Telegram:
#    "TODO: Buy groceries"

# 2. Обработать inbox
kira inbox

# 3. Проверить что создалось
ls vault/tasks/

# 4. Далее как в варианте 1
```

### Вариант 3: Ручное создание

```bash
# Создать файл напрямую
cat > vault/inbox/task.txt << 'EOF'
Купить молоко завтра к 18:00
EOF

# Обработать
kira inbox

# Проверить результат
ls vault/tasks/
```

---

## 🔧 Troubleshooting

### "kira: command not found"

```bash
# Решение:
poetry shell  # Активировать venv
```

### Import errors

```bash
# Решение:
poetry install --no-cache
```

### Vault not found

```bash
# Решение:
kira vault init  # Создать структуру
```

---

## 📚 Что дальше?

После успешного Quick Start:

1. **Прочитать полный setup:**
   - [SETUP_GUIDE.md](docs/SETUP_GUIDE.md) - детальная настройка
   
2. **Изучить возможности:**
   - [CLI Documentation](docs/cli.md) - все команды
   - [Configuration Guide](config/README.md) - настройка
   
3. **Проверить готовность:**
   - [READINESS_CHECKLIST.md](docs/READINESS_CHECKLIST.md) - что работает
   
4. **Разработать плагины:**
   - [SDK Documentation](docs/sdk.md) - API для плагинов
   
5. **Настроить автоматизацию:**
   ```bash
   # Добавить в crontab
   */5 * * * * cd ~/Projects/kira-project && poetry run kira inbox
   ```

---

## 🎉 Поздравляю!

Вы запустили Kira и готовы к использованию!

**Полезные ссылки:**
- 📖 [Full Setup Guide](docs/SETUP_GUIDE.md)
- 📋 [Readiness Checklist](docs/READINESS_CHECKLIST.md)
- 🎨 [Architecture Docs](docs/architecture.md)
- 🔧 [Configuration](config/README.md)

**Вопросы?** Откройте issue или см. документацию.

