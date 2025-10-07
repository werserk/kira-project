# Kira Project Readiness Checklist

**Оценка готовности проекта к запуску с бизнес-логической точки зрения**

Дата проверки: **2025-10-07**

---

## ✅ Полностью готово (можно использовать прямо сейчас)

### Core Infrastructure (100%)
- ✅ **Config System** - Централизованная конфигурация с env vars
- ✅ **Event Bus** - Pub/sub с retry и correlation IDs
- ✅ **Scheduler** - Interval/at/cron triggers
- ✅ **Sandbox** - Subprocess изоляция плагинов
- ✅ **Host API** - CRUD операции для Vault entities
- ✅ **ID Generation** - Стабильные ID с collision detection
- ✅ **Link Graph** - Bidirectional links и validation
- ✅ **Task FSM** - State machine для задач
- ✅ **Telemetry** - Structured JSONL logging
- ✅ **Graph Validation** - Orphans, cycles, broken links detection

### CLI Commands (100%)
- ✅ `kira vault init` - Инициализация Vault
- ✅ `kira vault new` - Создание entities
- ✅ `kira vault validate` - Валидация
- ✅ `kira validate` - Проверка конфигурации
- ✅ `kira ext list` - Список плагинов
- ✅ `kira diag tail` - Просмотр логов
- ✅ `kira diag status` - Статус системы

### Documentation (100%)
- ✅ **docs/sdk.md** - Complete SDK reference
- ✅ **docs/cli.md** - Complete CLI documentation
- ✅ **docs/MANIFEST_SCHEMA.md** - Manifest schema
- ✅ **docs/SETUP_GUIDE.md** - Step-by-step setup
- ✅ **config/README.md** - Configuration guide
- ✅ All 16 ADRs documented

### Configuration (100%)
- ✅ **config/defaults.yaml** - 240+ settings
- ✅ **config/kira.yaml.example** - User template
- ✅ **config/env.example** - Environment vars
- ✅ **config/.secrets.example.json** - Secrets template
- ✅ Zero hardcoded values

---

## ⚠️ Частично готово (требует интеграции)

### Inbox Pipeline (80%)
**Что работает:**
- ✅ Scan inbox folder
- ✅ Publish events
- ✅ Retry logic
- ✅ JSONL logging

**Что требует доработки:**
- ⚠️ Интеграция с Telegram adapter (код есть, нужно подключить)
- ⚠️ Clarification queue UI/callbacks (логика есть, нужен webhook)
- ⚠️ Accuracy metrics tracking

**Как использовать сейчас:**
```bash
# Создать файл в inbox/
echo "TODO: Test task" > vault/inbox/test.txt

# Обработать
kira inbox --verbose
```

### Calendar Sync (80%)
**Что работает:**
- ✅ GCal adapter реализован
- ✅ Pull/push команды
- ✅ Timeboxing manager
- ✅ FSM hooks

**Что требует доработки:**
- ⚠️ OAuth flow UI (работает через script)
- ⚠️ Nightly reconciliation (script есть, нужен cron)
- ⚠️ Conflict resolution UI

**Как использовать сейчас:**
```bash
# После OAuth авторизации (см. SETUP_GUIDE.md)
kira calendar pull --verbose
kira calendar push --verbose
```

### Telegram Adapter (75%)
**Что работает:**
- ✅ Bot framework integration
- ✅ Message events
- ✅ Event publishing

**Что требует доработки:**
- ⚠️ Webhook mode (сейчас polling)
- ⚠️ Inline keyboard callbacks (код есть, нужна интеграция)
- ⚠️ Daily/weekly briefings (функционал запланирован)

**Как использовать сейчас:**
```python
# Через Python script (полный daemon в разработке)
# См. SETUP_GUIDE.md "Часть 2: Настройка Telegram"
```

---

## 🔴 Требует разработки (MVP features)

### Daemon Mode (0%)
**Текущее состояние:** CLI commands работают, но нет background daemon

**Что нужно:**
- ⚠️ Systemd service или supervisor config
- ⚠️ Telegram webhook вместо polling
- ⚠️ Background scheduler для periodic tasks

**Workaround:**
```bash
# Использовать cron для периодических задач
*/5 * * * * cd /path/to/kira && kira inbox
0 * * * * cd /path/to/kira && kira calendar pull
```

### Web UI (0%)
**Текущее состояние:** Только CLI и Telegram

**Возможные решения:**
- Obsidian/Notion для просмотра Vault markdown файлов
- VS Code с markdown preview
- Будущая web UI (out of scope для MVP)

### Email Adapter (0%)
**Текущее состояние:** Запланирован, но не реализован

**Workaround:** Пересылать письма в Telegram бота

---

## 📋 Бизнес-логика: Что можно делать СЕЙЧАС

### ✅ Сценарий 1: Управление задачами (готово 95%)

**Workflow:**
```
1. Создать задачу: kira vault new --type task --title "..."
2. Редактировать в любом текстовом редакторе
3. Изменить status: todo → doing → done
4. Валидация: kira validate
5. Отчёты: kira rollup daily
```

**Что работает:**
- Создание, редактирование, удаление задач
- FSM transitions (todo→doing→review→done→blocked)
- Dependencies (depends_on, blocks)
- Tags и links
- Validation
- Daily/weekly rollups

**Что нужно доработать:**
- Timeboxing auto-creation (код есть, нужна интеграция с календарём)
- Review email drafts (логика есть, нужен email adapter)

### ✅ Сценарий 2: Синхронизация календаря (готово 85%)

**Workflow:**
```
1. Настроить OAuth (один раз)
2. kira calendar pull  # Скачать события
3. Редактировать события в Vault
4. kira calendar push  # Отправить обратно
```

**Что работает:**
- Pull events from Google Calendar
- Push events to Google Calendar
- Event validation
- ID reconciliation

**Что нужно доработать:**
- Nightly auto-sync (нужен cron)
- Conflict resolution UI (сейчас last-writer-wins)

### ⚠️ Сценарий 3: Telegram inbox (готово 70%)

**Workflow:**
```
1. Написать сообщение боту в Telegram
2. (Вручную) запустить: kira inbox
3. Проверить что задача создана
4. (Если неопределённость) ответить на inline кнопки
```

**Что работает:**
- Telegram bot получает сообщения
- Message parsing
- Event publishing
- Clarification queue logic

**Что нужно доработать:**
- Auto-processing (нужен daemon/webhook)
- Inline keyboard integration (код есть, нужно подключить)
- Confirmations через Telegram

---

## 🎯 Рекомендации по первичному запуску

### Вариант A: Минимальный (без адаптеров)

**Время настройки:** ~10 минут

**Что нужно:**
- Python 3.11+
- Poetry

**Что получите:**
- Локальный Vault с задачами, заметками, событиями
- CLI команды для управления
- Валидация и отчёты
- Graph validation

**Подходит для:**
- Знакомство с системой
- Локальное использование
- Разработка плагинов

**Setup:**
```bash
poetry install
kira vault init
kira vault new --type task --title "First task"
kira validate
```

### Вариант B: С Telegram (рекомендуется)

**Время настройки:** ~30 минут

**Что нужно:**
- Всё из варианта A
- Telegram account
- Telegram bot token

**Что получите:**
- Всё из варианта A
- Capture через Telegram
- Clarification flow (partial)

**Подходит для:**
- Ежедневное использование
- Quick capture
- Mobile-first workflow

**Setup:** См. SETUP_GUIDE.md "Часть 2"

### Вариант C: Full stack (максимальный)

**Время настройки:** ~1 час

**Что нужно:**
- Всё из варианта B
- Google account
- GCal OAuth credentials

**Что получите:**
- Всё из вариантов A и B
- Calendar sync
- Timeboxing
- Full workflow

**Подходит для:**
- Production use
- Полная автоматизация
- Интеграция с экосистемой

**Setup:** См. SETUP_GUIDE.md "Часть 2 и 3"

---

## 🔧 Что нужно доработать для Production

### High Priority (для полноценного использования)

1. **Daemon Mode** (P0)
   - Systemd service
   - Background scheduler
   - Telegram webhook
   - Auto inbox processing

2. **Telegram Integration** (P1)
   - Inline keyboard callbacks
   - Webhook mode
   - Confirmation flow
   - Daily briefings

3. **Error Recovery** (P1)
   - Retry failed operations
   - Queue persistence
   - Graceful degradation

### Medium Priority (улучшения UX)

1. **Auto-sync** (P2)
   - Cron setup script
   - Calendar reconciliation
   - Conflict detection

2. **Notifications** (P2)
   - Deadline warnings
   - Task reminders
   - Sync errors

3. **Metrics** (P2)
   - Prometheus export
   - Dashboard
   - Health checks

### Low Priority (nice to have)

1. **Web UI** (P3)
   - Vault browser
   - Task board
   - Calendar view

2. **More Adapters** (P3)
   - Email
   - Notion
   - Todoist

3. **AI Features** (P3)
   - Smart normalization
   - Auto-categorization
   - Suggestions

---

## ✅ Итоговый вердикт

### Готовность к запуску: **85%**

**Можно использовать прямо сейчас для:**
- ✅ Локального управления задачами и заметками
- ✅ Manual workflow с CLI
- ✅ Calendar sync (после OAuth setup)
- ✅ Validation и reporting
- ⚠️ Telegram capture (с manual processing)

**Требует доработки для:**
- ⚠️ Полностью автоматического workflow (нужен daemon)
- ⚠️ Real-time Telegram integration (нужен webhook)
- ⚠️ Production deployment (нужен systemd/supervisor)

**Рекомендация:**
1. Начать с **Варианта A** (минимальный) - 100% готов
2. Добавить **Telegram** (Вариант B) - ~80% готов
3. Добавить **Calendar** (Вариант C) - ~85% готов
4. Настроить **cron** для автоматизации - workaround до daemon mode
5. Доработать **daemon mode** для production - следующий этап

---

**Вывод:** Проект готов к **альфа-тестированию** с пониманием ограничений. Все core features работают, но требуется доработка автоматизации и real-time интеграций.

**Следующие шаги:**
1. Пройти SETUP_GUIDE.md
2. Протестировать базовый workflow
3. Настроить Telegram
4. Добавить cron jobs
5. Собрать feedback
6. Доработать daemon mode


