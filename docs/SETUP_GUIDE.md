# Kira Setup Guide - Первичная настройка и запуск

**Полное руководство по развёртыванию Kira с нуля до первого реального использования**

## 📋 Предварительные требования

### Системные требования

- **Python 3.11+** (обязательно)
- **Poetry** (рекомендуется) или pip
- **Git** для клонирования
- **Telegram аккаунт** (для Telegram адаптера)
- **Google аккаунт** (для Calendar адаптера)

### Проверка Python

```bash
python3 --version  # Должно быть 3.11 или выше
```

### Установка Poetry (если нет)

```bash
curl -sSL https://install.python-poetry.org | python3 -
# Или
pip install poetry
```

---

## 🚀 Часть 1: Базовая установка (без адаптеров)

### Шаг 1: Клонирование и установка

```bash
# Клонировать репозиторий (если ещё не сделали)
cd ~/Projects
git clone <repository-url> kira-project
cd kira-project

# Установить базовые зависимости
poetry install

# Или через pip (без Poetry)
pip install -e .
```

### Шаг 2: Проверка установки

```bash
# Активировать виртуальное окружение Poetry
poetry shell

# Проверить что CLI работает
kira --help

# Должен показать список доступных команд:
# inbox, calendar, rollup, vault, ext, plugin, code, validate
```

**Ожидаемый вывод:**

```
Kira - система управления знаниями и задачами

Commands:
  calendar   Команды для работы с календарём
  code       Команды для работы с кодом
  ext        Управление расширениями
  inbox      Обработка inbox
  plugin     Работа с плагинами
  rollup     Генерация отчётов
  validate   Валидация Vault
  vault      Управление Vault
```

### Шаг 3: Создание конфигурации

```bash
# Скопировать example конфигурацию
cp config/kira.yaml.example kira.yaml

# Открыть и настроить базовые параметры
nano kira.yaml  # или vim, code, etc.
```

**Минимальная конфигурация в `kira.yaml`:**

```yaml
# Базовая настройка без адаптеров
vault:
  path: "vault"  # Или абсолютный путь

core:
  timezone: "Europe/Moscow"  # Ваш часовой пояс

plugins:
  enabled: []  # Пока пусто, добавим позже

logging:
  level: "INFO"
  console_output: true

# Адаптеры отключены
adapters:
  telegram:
    enabled: false
  gcal:
    enabled: false
```

### Шаг 4: Инициализация Vault

```bash
# Создать структуру Vault
kira vault init

# Проверить что создалось
ls -la vault/
```

**Должно быть создано:**

```
vault/
├── .kira/
│   └── schemas/      # JSON схемы для валидации
├── inbox/            # Необработанные items
├── tasks/            # Задачи
├── notes/            # Заметки
├── events/           # События
├── projects/         # Проекты
└── @Indexes/         # Индексы и отчёты
```

### Шаг 5: Первый тест - создание задачи

```bash
# Создать тестовую задачу
kira vault new \
  --type task \
  --title "Протестировать Kira" \
  --verbose

# Проверить что задача создана
ls vault/tasks/

# Посмотреть содержимое
cat vault/tasks/task-*.md
```

**Ожидаемое содержимое файла:**

```markdown
---
id: task-20251007-2330-prote

stirovat-kira
title: Протестировать Kira
status: todo
created: 2025-10-07T23:30:00+03:00
updated: 2025-10-07T23:30:00+03:00
---

# Протестировать Kira

<!-- Описание задачи -->
```

### Шаг 6: Валидация

```bash
# Проверить что всё правильно
kira validate

# Должно быть:
# ✅ Configuration valid: kira.yaml
# ✅ Vault structure valid
```

**✅ Поздравляю! Базовая установка завершена.**

---

## 📱 Часть 2: Настройка Telegram адаптера (опционально)

### Шаг 1: Установка зависимостей

```bash
# С Poetry
poetry install --extras telegram

# Или с pip
pip install python-telegram-bot httpx
```

### Шаг 2: Создание Telegram бота

1. **Открыть Telegram и найти @BotFather**

2. **Создать нового бота:**
   ```
   /newbot
   ```

3. **Задать имя:**
   ```
   Kira Personal Assistant
   ```

4. **Задать username** (должен заканчиваться на 'bot'):
   ```
   your_kira_bot
   ```

5. **Сохранить токен**, который вернул BotFather:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### Шаг 3: Получение Chat ID

```bash
# Способ 1: Через Python
python3 << 'EOF'
import asyncio
from telegram import Bot

async def get_chat_id():
    bot = Bot("YOUR_BOT_TOKEN")
    updates = await bot.get_updates()
    if updates:
        print(f"Your Chat ID: {updates[0].message.chat.id}")
    else:
        print("Send any message to your bot first, then run this again")

asyncio.run(get_chat_id())
EOF

# Способ 2: Написать боту /start в Telegram, 
# потом открыть: https://api.telegram.org/bot<TOKEN>/getUpdates
```

### Шаг 4: Настройка окружения

```bash
# Создать .env файл
cp config/env.example .env

# Отредактировать .env
nano .env
```

**В `.env` добавить:**

```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
TELEGRAM_MODE=bot
```

### Шаг 5: Включить Telegram в конфигурации

```bash
# Отредактировать kira.yaml
nano kira.yaml
```

```yaml
plugins:
  enabled:
    - kira-inbox  # Активировать inbox plugin

adapters:
  telegram:
    enabled: true
    mode: "bot"
    whitelist_chats: []  # Пусто = все чаты разрешены
```

### Шаг 6: Тестирование Telegram

```bash
# Запустить Telegram адаптер (в отдельном терминале)
# NOTE: Полная реализация требует daemon mode, 
# пока можно тестировать через Python

python3 << 'EOF'
import asyncio
import os
from telegram import Bot

async def test_bot():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    bot = Bot(token)
    me = await bot.get_me()
    print(f"✅ Bot connected: @{me.username}")
    
    # Отправить тестовое сообщение
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    await bot.send_message(
        chat_id=chat_id,
        text="🤖 Kira bot is ready!\n\nSend me tasks and I'll organize them."
    )
    print(f"✅ Test message sent to chat {chat_id}")

asyncio.run(test_bot())
EOF
```

**Если всё работает, в Telegram придёт сообщение от бота!**

### Шаг 7: Тест inbox через Telegram

1. **Написать боту в Telegram:**
   ```
   TODO: Купить молоко завтра к 18:00
   ```

2. **Запустить inbox pipeline:**
   ```bash
   kira inbox --verbose
   ```

3. **Проверить результат:**
   ```bash
   # Должен был создаться файл в inbox/
   ls vault/inbox/
   
   # Или в tasks/ если нормализация сработала
   ls vault/tasks/
   ```

---

## 📅 Часть 3: Настройка Google Calendar (опционально)

### Шаг 1: Установка зависимостей

```bash
# С Poetry
poetry install --extras gcal

# Или с pip
pip install google-auth google-auth-oauthlib google-api-python-client
```

### Шаг 2: Получение credentials

1. **Открыть [Google Cloud Console](https://console.cloud.google.com/)**

2. **Создать новый проект или выбрать существующий**

3. **Включить Google Calendar API:**
   - APIs & Services → Library
   - Найти "Google Calendar API"
   - Нажать "Enable"

4. **Создать OAuth credentials:**
   - APIs & Services → Credentials
   - Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Name: Kira Calendar Sync
   - Download JSON

5. **Сохранить credentials:**
   ```bash
   mkdir -p .credentials
   mv ~/Downloads/client_secret_*.json .credentials/gcal_credentials.json
   ```

### Шаг 3: Первичная авторизация

```bash
# Запустить авторизацию
python3 << 'EOF'
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pickle

SCOPES = ['https://www.googleapis.com/auth/calendar']

creds = None
token_path = '.credentials/gcal_token.pickle'

if os.path.exists(token_path):
    with open(token_path, 'rb') as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            '.credentials/gcal_credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    
    with open(token_path, 'wb') as token:
        pickle.dump(creds, token)
    
    print("✅ Authorization successful!")
    print(f"✅ Token saved to {token_path}")
else:
    print("✅ Already authorized!")
EOF
```

**Откроется браузер для авторизации. Разрешите доступ.**

### Шаг 4: Настройка конфигурации

```yaml
# В kira.yaml
plugins:
  enabled:
    - kira-inbox
    - kira-calendar  # Добавить

  calendar:
    default_calendar_id: "primary"
    sync_days_future: 30
    timebox_default_minutes: 25

adapters:
  gcal:
    enabled: true
    credentials_path: ".credentials/gcal_credentials.json"
    token_path: ".credentials/gcal_token.pickle"
```

### Шаг 5: Тест синхронизации

```bash
# Pull events from Google Calendar
kira calendar pull --verbose

# Проверить что события скачались
ls vault/events/

# Посмотреть одно из событий
cat vault/events/event-*.md
```

---

## 🧪 Часть 4: End-to-End тестирование

### Сценарий 1: Полный цикл задачи через Telegram

**Шаги:**

1. **Отправить в Telegram боту:**
   ```
   TODO: Написать отчёт по проекту к пятнице
   ```

2. **Запустить inbox:**
   ```bash
   kira inbox --verbose
   ```

3. **Проверить что задача создана:**
   ```bash
   ls vault/tasks/
   cat vault/tasks/task-*otchet*.md
   ```

4. **Изменить статус задачи:**
   ```bash
   # Открыть файл и изменить status: todo → doing
   nano vault/tasks/task-*otchet*.md
   ```

5. **Проверить FSM transition (если настроен timeboxing):**
   ```bash
   # Timebox должен быть создан в календаре
   kira calendar push --verbose
   ```

### Сценарий 2: Синхронизация с Google Calendar

**Шаги:**

1. **Создать событие в Google Calendar:**
   - Название: "Встреча с командой"
   - Время: Завтра 14:00-15:00

2. **Синхронизировать:**
   ```bash
   kira calendar pull
   ```

3. **Проверить в Vault:**
   ```bash
   grep -r "Встреча с командой" vault/events/
   ```

4. **Изменить в Vault и push обратно:**
   ```bash
   # Изменить время или описание в .md файле
   nano vault/events/event-*.md
   
   # Отправить обратно в GCal
   kira calendar push
   ```

### Сценарий 3: Inbox → Clarification → Confirmation

**Шаги:**

1. **Отправить неоднозначное сообщение:**
   ```
   Встреча завтра
   ```

2. **Запустить inbox с низким threshold:**
   ```bash
   # В kira.yaml установить:
   # plugins.inbox.confidence_threshold: 0.9
   
   kira inbox --verbose
   ```

3. **Проверить очередь clarifications:**
   ```bash
   # Если реализована, должна быть:
   ls vault/.kira/clarifications.json
   cat vault/.kira/clarifications.json
   ```

4. **Bot отправит inline кнопки в Telegram:**
   - "✅ Yes, it's an event"
   - "📝 No, it's a task"
   - "❌ Ignore"

### Сценарий 4: Daily Rollup

**Шаги:**

1. **Создать несколько задач и событий**

2. **Сгенерировать daily rollup:**
   ```bash
   kira rollup daily --verbose
   ```

3. **Проверить отчёт:**
   ```bash
   cat vault/@Indexes/daily-$(date +%Y%m%d).md
   ```

**Ожидаемое содержимое:**

```markdown
# Daily Rollup - 2025-10-07

## Tasks
- ✅ Completed: 2
- 🔄 In Progress: 1
- 📋 Todo: 3

## Events
- 📅 Total: 5
- ⏰ Upcoming: 2

## Summary
...
```

### Сценарий 5: Graph Validation

**Шаги:**

1. **Создать задачи с зависимостями:**
   ```bash
   # Задача A
   kira vault new --type task --title "Task A"
   
   # Задача B (зависит от A)
   # Открыть файл и добавить в frontmatter:
   # depends_on: [task-A-id]
   ```

2. **Запустить валидацию:**
   ```bash
   python3 scripts/nightly_validation.py
   ```

3. **Проверить отчёт:**
   ```bash
   cat vault/@Indexes/graph_report.md
   ```

---

## 🔧 Troubleshooting

### Проблема: "kira: command not found"

**Решение:**

```bash
# С Poetry
poetry shell  # Активировать venv

# Или полный путь
poetry run kira --help

# Или установить глобально
poetry build
pip install dist/kira-*.whl
```

### Проблема: Import errors

**Решение:**

```bash
# Переустановить в development mode
poetry install --with dev

# Проверить PYTHONPATH
echo $PYTHONPATH

# Должен включать src/
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

### Проблема: Telegram bot не отвечает

**Диагностика:**

```bash
# Проверить токен
curl https://api.telegram.org/bot<TOKEN>/getMe

# Проверить updates
curl https://api.telegram.org/bot<TOKEN>/getUpdates

# Проверить .env загружен
python3 -c "import os; print(os.environ.get('TELEGRAM_BOT_TOKEN'))"
```

### Проблема: Google Calendar авторизация failed

**Решение:**

```bash
# Удалить старый token
rm .credentials/gcal_token.pickle

# Повторить авторизацию
# (см. Часть 3, Шаг 3)

# Проверить что credentials файл правильный
cat .credentials/gcal_credentials.json | jq '.installed'
```

### Проблема: Валидация не проходит

**Диагностика:**

```bash
# Детальная валидация
kira validate --verbose

# Проверить конкретный тип
kira vault validate --type task

# Посмотреть логи
tail -f logs/core/validation.jsonl
```

---

## 📊 Monitoring и Logs

### Просмотр логов

```bash
# Tail all logs
kira diag tail --follow

# Tail specific component
kira diag tail --component core

# Filter by level
kira diag tail --level error

# Follow specific trace
kira diag tail --trace-id abc-123-def
```

### Проверка системы

```bash
# System status
kira diag status

# Vault statistics
kira vault info

# Plugin status
kira ext list
```

---

## 🎯 Что дальше?

После успешной настройки вы можете:

1. **Настроить автоматизацию:**
   ```bash
   # Добавить в crontab
   crontab -e
   
   # Каждые 5 минут inbox
   */5 * * * * cd /path/to/kira && poetry run kira inbox
   
   # Каждый час calendar sync
   0 * * * * cd /path/to/kira && poetry run kira calendar pull
   
   # Каждую ночь валидация
   0 2 * * * cd /path/to/kira && python3 scripts/nightly_validation.py
   ```

2. **Настроить Telegram webhook** (вместо polling)

3. **Создать свои плагины** (см. docs/sdk.md)

4. **Интегрировать с другими системами** (email, Notion, etc.)

---

## 📚 Дополнительные ресурсы

- [CLI Documentation](cli.md)
- [SDK Documentation](sdk.md)
- [Configuration Guide](../config/README.md)
- [ADR Documentation](adr/)

---

**Последнее обновление:** 2025-10-07  
**Версия:** 1.0.0

**Вопросы?** Откройте issue на GitHub или обратитесь к документации.

