# Hot Reload для быстрой разработки

## Как работает Hot Reload

В dev-окружении (`compose.dev.yaml`) код **автоматически примонтирован** в контейнер:

```yaml
volumes:
  # Hot-reload: mount source code (read-write for auto-reload)
  - ./src/kira:/app/src/kira:rw
```

Это значит, что **изменения в коде сразу доступны в контейнере** без пересборки образа!

## Быстрый workflow разработки

### 1. Редактируй код

```bash
# Редактируй любой файл в src/kira/
vim src/kira/agent/nodes.py
```

### 2. Применяй изменения

**Вариант A: Быстрый перезапуск** (рекомендуется)
```bash
make restart
```

**Вариант B: Вручную**
```bash
make down
make up
```

**Вариант C: Только перезапуск контейнера**
```bash
docker restart kira-telegram-dev
```

### 3. Проверяй логи

```bash
make logs
# или
docker logs -f kira-telegram-dev
```

## Когда нужен rebuild

Используй `make rebuild` **только** если изменил:

- ❌ Код в `src/kira/` → **НЕТ**, используй `make restart`
- ✅ `pyproject.toml` (зависимости) → **ДА**, используй `make rebuild`
- ✅ `Dockerfile.dev` → **ДА**, используй `make rebuild`
- ✅ System packages → **ДА**, используй `make rebuild`
- ❌ Конфигурацию в `.env` → **НЕТ**, используй `make restart`

## Сравнение команд

| Команда | Время | Когда использовать |
|---------|-------|-------------------|
| `make restart` | ~10 сек | **Изменения кода** (ежедневная работа) |
| `make rebuild` | ~2-3 мин | Изменения зависимостей/Dockerfile |
| `docker restart` | ~5 сек | Самый быстрый, но без down/up |

## Автоматический Hot Reload (опционально)

Для **полностью автоматического** перезапуска при изменениях кода, можно настроить watchdog:

### Вариант 1: watchmedo (уже установлен в контейнере)

Измени команду в `compose.dev.yaml`:

```yaml
# Вместо:
command: poetry run kira telegram start --verbose

# Используй:
command: >
  watchmedo auto-restart
  --directory=/app/src/kira
  --pattern=*.py
  --recursive
  -- poetry run kira telegram start --verbose
```

### Вариант 2: nodemon (требует установки)

```bash
# В контейнере
pip install nodemon
nodemon --watch /app/src/kira --exec "poetry run kira telegram start --verbose"
```

## Проблемы и решения

### Изменения не применяются

**Проблема**: Редактировал код, но Кира использует старую версию

**Решение**:
```bash
# 1. Убедись, что используешь dev окружение
make down
ENV=dev make up

# 2. Проверь volume mapping
docker inspect kira-telegram-dev | grep -A5 Mounts

# 3. Перезапусти контейнер
make restart
```

### "Permission denied" при редактировании

**Проблема**: Не могу редактировать файлы после запуска контейнера

**Решение**:
```bash
# Верни права владельца
sudo chown -R $USER:$USER src/kira/
```

### Кеширование Python imports

**Проблема**: Python кеширует импорты, изменения не видны

**Решение**:
- Перезапусти контейнер: `make restart`
- Или используй `importlib.reload()` для hot-reload модулей

## Best Practices

### ✅ DO

- Используй `make restart` для изменений кода
- Редактируй файлы локально (не в контейнере)
- Проверяй логи после каждого изменения
- Коммитируй только работающий код

### ❌ DON'T

- Не используй `make rebuild` для каждого изменения
- Не редактируй файлы внутри контейнера
- Не забывай проверять логи на ошибки
- Не коммитируй без тестирования

## Примеры

### Пример 1: Исправление бага

```bash
# 1. Редактируем код
vim src/kira/agent/nodes.py

# 2. Применяем
make restart

# 3. Проверяем логи
make logs

# 4. Тестируем в Telegram
# Отправляем сообщение боту...

# 5. Если ок - коммитим
git add src/kira/agent/nodes.py
git commit -m "fix: исправлен баг с удалением задач"
```

### Пример 2: Добавление фичи

```bash
# 1. Создаем ветку
git checkout -b feature/new-tool

# 2. Редактируем код
vim src/kira/agent/kira_tools.py

# 3. Быстро тестируем с restart
make restart
# ... тестируем ...

# 4. Повторяем цикл edit -> restart -> test
# пока фича не готова

# 5. Коммитим
git commit -am "feat: добавлен новый инструмент"
```

## Мониторинг производительности

### Время перезапуска

```bash
# Замер времени restart
time make restart

# Обычно:
# - make restart: ~10 секунд
# - make rebuild: ~2-3 минуты
```

### Автоматизация с помощью alias

Добавь в `~/.bashrc`:

```bash
alias kr='make restart'
alias kl='make logs'
alias kd='make down'
alias ku='make up'
```

Теперь можно:
```bash
kr  # вместо make restart
kl  # вместо make logs
```

---

**TL;DR**: Редактируй код → `make restart` → Profit! 🚀

