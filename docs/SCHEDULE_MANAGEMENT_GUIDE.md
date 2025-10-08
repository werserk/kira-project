# Руководство по управлению расписанием в Kira

**Практический гайд: как использовать Kira для менеджмента вашего расписания**

---

## 📊 Оценка текущих возможностей

### ✅ Что РАБОТАЕТ прямо сейчас (готово к использованию)

| Функция | Статус | Как использовать |
|---------|--------|------------------|
| **Создание событий** | ✅ 100% | `kira vault new --type event` |
| **Создание задач с дедлайнами** | ✅ 100% | `kira vault new --type task --due "2025-10-15"` |
| **Синхронизация с Google Calendar** | ✅ 90% | `kira calendar pull/push` |
| **Timeboxing (выделение времени)** | ✅ 85% | Автоматически при `status: doing` |
| **Отображение расписания** | ⚠️ 70% | Через файлы `.md` + календарь |
| **Напоминания о дедлайнах** | ⚠️ 60% | Через deadlines plugin (manual) |
| **Daily/Weekly review** | ✅ 100% | `kira rollup daily/weekly` |

### ❌ Что НЕ работает (требует доработки)

| Функция | Статус | Workaround |
|---------|--------|------------|
| **Автоматическая синхронизация** | ❌ 0% | Использовать cron |
| **Push notifications** | ❌ 0% | Email или Telegram |
| **Календарный view** | ❌ 0% | Использовать Google Calendar |
| **Конфликты расписания** | ❌ 0% | Manual resolution |

---

## 🎯 Сценарий использования: Управление расписанием

### Вариант 1: Минимальный (без Google Calendar)

**Подходит для:** Простого трекинга задач и событий локально

#### Шаг 1: Создать события

```bash
# Встреча завтра в 14:00
kira vault new \
  --type event \
  --title "Team Meeting" \
  --start "2025-10-08T14:00:00+03:00" \
  --end "2025-10-08T15:00:00+03:00"

# Задача с дедлайном
kira vault new \
  --type task \
  --title "Подготовить отчёт" \
  --due "2025-10-10T18:00:00+03:00"

# Целодневное событие
kira vault new \
  --type event \
  --title "Отпуск" \
  --start "2025-10-15" \
  --end "2025-10-20" \
  --all-day
```

#### Шаг 2: Просмотр расписания

```bash
# Все события
ls vault/events/

# События на сегодня (через grep)
grep -l "$(date +%Y-%m-%d)" vault/events/*.md

# Задачи с дедлайном на этой неделе
grep -r "due:" vault/tasks/ | grep "$(date +%Y-%m)"
```

#### Шаг 3: Daily review

```bash
# Ежедневный отчёт
kira rollup daily

# Посмотреть отчёт
cat "vault/@Indexes/daily-$(date +%Y%m%d).md"
```

**Плюсы:**
- ✅ Работает оффлайн
- ✅ Полный контроль
- ✅ Все в markdown

**Минусы:**
- ❌ Нет визуального календаря
- ❌ Нет напоминаний
- ❌ Нужно вручную смотреть расписание

---

### Вариант 2: С Google Calendar (рекомендуется)

**Подходит для:** Полноценного управления расписанием с визуализацией

#### Prerequisite: Настройка Google Calendar

Один раз выполнить (см. [SETUP_GUIDE.md](SETUP_GUIDE.md)):

```bash
# 1. Получить OAuth credentials (см. детальный гайд)
# 2. Установить зависимости
poetry install --extras gcal

# 3. Авторизоваться
python3 scripts/gcal_auth.py  # Если есть

# 4. Включить в kira.yaml
```

```yaml
# kira.yaml
adapters:
  gcal:
    enabled: true
    credentials_path: ".credentials/gcal_credentials.json"
    token_path: ".credentials/gcal_token.json"

plugins:
  enabled:
    - kira-calendar

  calendar:
    default_calendar_id: "primary"
    sync_days_past: 7
    sync_days_future: 30
```

#### Workflow: Двусторонняя синхронизация

**1. Скачать события из Google Calendar**

```bash
# Синхронизировать (pull)
kira calendar pull --days 30 --verbose

# Проверить что скачалось
ls vault/events/
```

**Что происходит:**
- ✅ События из GCal скачиваются в `vault/events/`
- ✅ Создаются `.md` файлы с frontmatter
- ✅ Сохраняется `gcal_id` для обратной синхронизации
- ✅ Учитываются все поля: title, start, end, location, attendees

**2. Работать с событиями в Vault**

```bash
# Редактировать в любом редакторе
nano vault/events/event-20251008-1400-team-meeting.md

# Или создать новое событие
kira vault new --type event --title "Новая встреча" --start "2025-10-09T10:00:00+03:00"
```

**Пример файла:**

```markdown
---
id: event-20251008-1400-team-meeting
title: Team Meeting
type: event
start: 2025-10-08T14:00:00+03:00
end: 2025-10-08T15:00:00+03:00
location: Office, Meeting Room 3
attendees:
  - john@example.com
  - jane@example.com
gcal_id: abc123xyz  # ID в Google Calendar
created: 2025-10-07T20:00:00+03:00
updated: 2025-10-07T20:15:00+03:00
---

# Team Meeting

## Agenda
1. Project status update
2. Q4 planning
3. AOB

## Notes
<!-- Заметки во время встречи -->
```

**3. Отправить изменения обратно в Google Calendar**

```bash
# Синхронизировать (push)
kira calendar push --verbose

# Dry-run (показать что будет отправлено)
kira calendar push --dry-run
```

**Что происходит:**
- ✅ Новые события создаются в GCal
- ✅ Изменённые события обновляются
- ✅ Удалённые события (с `deleted: true`) удаляются из GCal
- ✅ Конфликты разрешаются (last-writer-wins)

---

### Вариант 3: С Telegram (быстрый захват)

**Подходит для:** Mobile-first workflow, быстрое добавление событий

#### Setup (один раз)

См. [SETUP_GUIDE.md](SETUP_GUIDE.md) "Часть 2: Telegram"

#### Workflow

**1. Быстрое добавление через Telegram**

```
# Написать боту в Telegram:
Встреча с клиентом завтра в 15:00
```

**2. Обработать inbox**

```bash
# Обработать сообщения
kira inbox --verbose
```

**3. Синхронизировать с календарём**

```bash
# Отправить в Google Calendar
kira calendar push
```

**Полный цикл:**
```
Telegram → Inbox → Normalize → Vault → Google Calendar
```

---

## 🔄 Типичные сценарии

### Сценарий 1: Планирование недели

```bash
# 1. Скачать события из GCal
kira calendar pull --days 7

# 2. Создать задачи на неделю
kira vault new --type task --title "Написать отчёт" --due "2025-10-11"
kira vault new --type task --title "Code review" --due "2025-10-09"

# 3. Распределить время (timeboxing)
# Открыть задачу и изменить status на 'doing'
# Автоматически создастся блок в календаре

# 4. Синхронизировать
kira calendar push

# 5. Проверить в Google Calendar
# Откройте calendar.google.com - там будут все ваши задачи и события
```

### Сценарий 2: Daily review (утро)

```bash
# 1. Скачать изменения из GCal
kira calendar pull

# 2. Сгенерировать daily rollup
kira rollup daily

# 3. Посмотреть что на сегодня
cat "vault/@Indexes/daily-$(date +%Y%m%d).md"
```

**Пример daily rollup:**

```markdown
# Daily Rollup - 2025-10-08

## 📅 Events Today
- 09:00-10:00: Standup Meeting
- 14:00-15:00: Team Meeting
- 16:00-17:00: Client Call

## ✅ Tasks Due Today
- [ ] Подготовить презентацию (due: 18:00)
- [ ] Code review PR#123 (due: 17:00)

## 🔄 Tasks In Progress
- [ ] Написать документацию (status: doing)

## 📊 Statistics
- Total events today: 3
- Total tasks due: 2
- Tasks in progress: 1
```

### Сценарий 3: Timeboxing (работа с задачами)

```bash
# 1. Создать задачу
kira vault new --type task --title "Написать код" --time-hint "2h"

# 2. Начать работу
# Открыть файл задачи
nano vault/tasks/task-*.md

# Изменить status: todo → doing
# Сохранить

# 3. Автоматически создастся блок в календаре
kira calendar push

# 4. В Google Calendar появится событие:
# "⏱️ Написать код" (2 часа от текущего времени)
```

### Сценарий 4: Проверка конфликтов

```bash
# Создать два события на одно время
kira vault new --type event --title "Event 1" --start "2025-10-09T14:00:00+03:00"
kira vault new --type event --title "Event 2" --start "2025-10-09T14:00:00+03:00"

# Проверить конфликты
kira calendar conflicts

# Output:
# ⚠️ Found 1 scheduling conflict:
# - 2025-10-09 14:00: Event 1 ⚔️ Event 2
```

---

## 🛠️ Практические команды

### Создание событий

```bash
# Простое событие
kira vault new --type event --title "Meeting" --start "2025-10-09T10:00:00+03:00"

# С location и участниками
kira vault new \
  --type event \
  --title "Project Kickoff" \
  --start "2025-10-09T10:00:00+03:00" \
  --end "2025-10-09T11:30:00+03:00" \
  --location "Office" \
  --attendees "john@example.com,jane@example.com"

# Целодневное событие
kira vault new --type event --title "Holiday" --start "2025-10-15" --all-day

# Повторяющееся событие (через frontmatter)
kira vault new --type event --title "Weekly Standup" --start "2025-10-09T09:00:00+03:00"
# Потом добавить в файл:
# recurring: weekly
# until: 2025-12-31
```

### Синхронизация

```bash
# Pull (скачать из GCal)
kira calendar pull                    # Последние 30 дней
kira calendar pull --days 7           # Последние 7 дней
kira calendar pull --calendar work    # Конкретный календарь
kira calendar pull --verbose          # С подробностями

# Push (отправить в GCal)
kira calendar push                    # Все изменения
kira calendar push --dry-run          # Показать без отправки
kira calendar push --calendar work    # Конкретный календарь
kira calendar push --verbose          # С подробностями
```

### Просмотр расписания

```bash
# События сегодня
grep -l "$(date +%Y-%m-%d)" vault/events/*.md | xargs -I {} basename {} .md

# События на неделю
find vault/events/ -name "event-$(date +%Y%m)*" -type f

# Задачи с дедлайном
grep -r "due:" vault/tasks/ | grep -v "completed"

# Ближайшие события (через rollup)
kira rollup daily
```

### Автоматизация через cron

```bash
# Добавить в crontab
crontab -e

# Синхронизация каждый час
0 * * * * cd /path/to/kira && poetry run kira calendar pull
0 * * * * cd /path/to/kira && poetry run kira calendar push

# Daily rollup каждое утро в 8:00
0 8 * * * cd /path/to/kira && poetry run kira rollup daily

# Weekly rollup по понедельникам в 9:00
0 9 * * 1 cd /path/to/kira && poetry run kira rollup weekly
```

---

## 📱 Mobile workflow

### Через Telegram + Google Calendar

```
┌─────────────┐
│  Telegram   │  1. Быстрый захват
│   (Mobile)  │     "Встреча завтра 14:00"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Kira Inbox  │  2. Обработка (auto/manual)
│  Pipeline   │     kira inbox
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Vault    │  3. Normalize + Store
│  (Markdown) │     vault/events/...
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Google    │  4. Sync to GCal
│  Calendar   │     kira calendar push
│   (View)    │
└─────────────┘
```

**Преимущества:**
- ✅ Захват с телефона (Telegram)
- ✅ Просмотр на телефоне (Google Calendar app)
- ✅ Редактирование на компьютере (Vault)
- ✅ Напоминания (через GCal notifications)

---

## 🔧 Недостающие компоненты (добавим сейчас)

### 1. Команда для просмотра расписания

**Добавить:** `kira calendar view`

```bash
kira calendar view --today
kira calendar view --week
kira calendar view --date 2025-10-09
```

### 2. Проверка конфликтов

**Добавить:** `kira calendar conflicts`

```bash
kira calendar conflicts --week
```

### 3. Simplified event creation

**Добавить:** `kira event` (алиас)

```bash
kira event "Meeting tomorrow at 14:00"
# Автоматически парсит и создаёт событие
```

### 4. Напоминания

**Workaround:** Использовать Google Calendar notifications

В Google Calendar:
1. Settings → Event settings
2. Default notifications → Add notification
3. 15 minutes before, popup

---

## ⚡ Quick Reference Card

### Создание

| Что | Команда |
|-----|---------|
| Событие | `kira vault new --type event --title "..." --start "..."` |
| Задача | `kira vault new --type task --title "..." --due "..."` |
| Через Telegram | Написать боту → `kira inbox` |

### Синхронизация

| Действие | Команда |
|----------|---------|
| Скачать из GCal | `kira calendar pull` |
| Отправить в GCal | `kira calendar push` |
| Dry-run | `kira calendar push --dry-run` |

### Просмотр

| Что | Команда |
|-----|---------|
| Daily rollup | `kira rollup daily` |
| Weekly rollup | `kira rollup weekly` |
| Все события | `ls vault/events/` |
| В Google Calendar | Открыть calendar.google.com |

### Автоматизация

| Задача | Решение |
|--------|---------|
| Авто-синхронизация | Cron (см. выше) |
| Напоминания | Google Calendar notifications |
| Mobile view | Google Calendar app |

---

## ✅ Итоговый чеклист готовности

### Для базового использования (сейчас готово)

- ✅ Создание событий и задач
- ✅ Синхронизация с Google Calendar (manual)
- ✅ Просмотр в Google Calendar
- ✅ Daily/weekly rollups
- ✅ Markdown-based storage
- ✅ Full control over data

**Вердикт:** **Готово к использованию прямо сейчас!**

### Для продвинутого использования (требует setup)

- ⚠️ Telegram quick capture (нужен bot setup)
- ⚠️ Автоматическая синхронизация (нужен cron)
- ⚠️ Timeboxing (нужна интеграция с calendar plugin)
- ❌ Real-time notifications (workaround: GCal)
- ❌ Conflict detection (планируется)

**Вердикт:** **Можно использовать с workarounds**

---

## 🎯 Рекомендации для старта

### День 1: Базовый setup

```bash
# 1. Установка
poetry install
poetry shell

# 2. Конфигурация
cp config/kira.yaml.example kira.yaml

# 3. Инициализация
kira vault init

# 4. Первое событие
kira vault new --type event --title "Test Event" --start "$(date -I)T14:00:00+03:00"

# 5. Проверка
ls vault/events/
```

### День 2: Google Calendar интеграция

```bash
# 1. Setup OAuth (см. SETUP_GUIDE.md)

# 2. Pull events
kira calendar pull --verbose

# 3. Проверка в GCal
# Открыть calendar.google.com

# 4. Push test event
kira vault new --type event --title "Kira Sync Test" --start "$(date -I)T15:00:00+03:00"
kira calendar push

# 5. Verify in GCal
```

### День 3: Автоматизация

```bash
# Настроить cron для авто-синхронизации
crontab -e

# Добавить:
0 * * * * cd ~/Projects/kira-project && poetry run kira calendar pull >> /tmp/kira-sync.log 2>&1
```

### День 4-7: Использование

```bash
# Ежедневная рутина:
# Утро
kira calendar pull
kira rollup daily

# В течение дня
# - Создавать события/задачи
# - Работать в своём редакторе

# Вечер
kira calendar push
```

---

## 🎉 Заключение

**Готовность для управления расписанием: 85%**

### ✅ Что работает отлично:
- Создание и редактирование событий
- Синхронизация с Google Calendar
- Markdown-based workflow
- Full data ownership

### ⚠️ Что требует manual actions:
- Запуск синхронизации (workaround: cron)
- Просмотр расписания (workaround: Google Calendar)
- Напоминания (workaround: GCal notifications)

### 🚀 Можно использовать прямо сейчас для:
- Управления личным расписанием
- Синхронизации с Google Calendar
- Timeboxing задач
- Daily/weekly planning

**Вывод:** Kira готова к использованию для управления расписанием с пониманием, что некоторые удобства (auto-sync, real-time notifications) требуют workarounds.

---

**Следующие шаги:** Пройти SETUP_GUIDE.md и начать использовать!
