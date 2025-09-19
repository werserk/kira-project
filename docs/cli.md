# CLI Kira

## Обзор

Kira предоставляет мощный командный интерфейс для управления системой через терминал. CLI поддерживает все основные операции: обработку inbox, синхронизацию календаря, создание отчетов и управление расширениями.

## Установка и настройка

### Быстрый старт

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd kira-project

# Сделайте скрипт исполняемым
chmod +x kira

# Запустите команду
./kira --help
```

### Использование через Makefile

```bash
# Показать все доступные команды
make help

# Запустить inbox-конвейер
make inbox

# Синхронизировать календарь
make calendar-pull
make calendar-push

# Создать отчеты
make rollup-daily
make rollup-weekly

# Управление расширениями
make ext-list
```

## Основные команды

### 1. Inbox - обработка входящих элементов

```bash
# Базовая обработка
./kira inbox

# Подробный вывод
./kira inbox --verbose

# Режим dry-run (показать что будет обработано)
./kira inbox --dry-run --verbose
```

**Опции:**
- `--verbose, -v` - подробный вывод
- `--dry-run` - показать что будет обработано без выполнения
- `--config` - путь к файлу конфигурации

### 2. Calendar - работа с календарем

```bash
# Синхронизация (получение данных)
./kira calendar pull

# Синхронизация (отправка данных)
./kira calendar push

# Синхронизация конкретного календаря
./kira calendar pull --calendar work

# Синхронизация за определенный период
./kira calendar pull --days 7

# Dry-run для отправки
./kira calendar push --dry-run --verbose
```

**Опции pull:**
- `--calendar` - конкретный календарь
- `--days` - количество дней (по умолчанию: 30)
- `--verbose, -v` - подробный вывод

**Опции push:**
- `--calendar` - конкретный календарь
- `--dry-run` - показать что будет отправлено
- `--verbose, -v` - подробный вывод

### 3. Rollup - создание отчетов

```bash
# Дневной отчет
./kira rollup daily

# Недельный отчет
./kira rollup weekly

# Отчет за конкретную дату
./kira rollup daily --date 2024-01-15

# Отчет за конкретную неделю
./kira rollup weekly --week 2024-W03

# Сохранение в файл
./kira rollup daily --output daily-report.md
```

**Опции:**
- `--date` - дата для дневного отчета (YYYY-MM-DD)
- `--week` - неделя для недельного отчета (YYYY-WW)
- `--output` - путь для сохранения отчета
- `--verbose, -v` - подробный вывод

### 4. Code - работа с кодом

```bash
# Анализ кода
./kira code analyze

# Индексация для поиска
./kira code index

# Поиск в коде
./kira code search "function_name"

# Поиск по типу
./kira code search "class" --type class

# Ограничение результатов
./kira code search "test" --limit 10
```

**Опции analyze:**
- `--path` - путь для анализа
- `--output` - файл для сохранения результатов
- `--verbose, -v` - подробный вывод

**Опции index:**
- `--rebuild` - пересоздать индекс с нуля
- `--verbose, -v` - подробный вывод

**Опции search:**
- `query` - поисковый запрос
- `--type` - тип поиска (function, class, variable, comment, all)
- `--limit` - максимальное количество результатов
- `--verbose, -v` - подробный вывод

### 5. Ext - управление расширениями

```bash
# Список всех расширений
./kira ext list

# Список только плагинов
./kira ext list --type plugins

# Список только включенных
./kira ext list --status enabled

# Информация о расширении
./kira ext info kira-calendar

# Включить расширение
./kira ext enable kira-calendar

# Отключить расширение
./kira ext disable kira-calendar

# Установить расширение
./kira ext install kira-new-plugin
```

**Опции list:**
- `--type` - тип расширений (plugins, adapters, all)
- `--status` - статус (enabled, disabled, all)
- `--verbose, -v` - подробный вывод

**Опции install:**
- `name` - имя расширения
- `--source` - источник установки
- `--verbose, -v` - подробный вывод

## Конфигурация

CLI использует файл `kira.yaml` для конфигурации. Основные настройки:

```yaml
vault:
  path: "/path/to/vault"
  tz: "Europe/Moscow"

adapters:
  telegram:
    enabled: true
  gcal:
    enabled: true
    calendars:
      work: "work@example.com"
      personal: "personal@example.com"

policies:
  mode: "Focus"
  confirm_external_writes: true
```

## Примеры использования

### Ежедневный workflow

```bash
# 1. Обработать inbox
make inbox

# 2. Синхронизировать календарь
make calendar-pull

# 3. Создать дневной отчет
make rollup-daily

# 4. Проверить статус расширений
make ext-list
```

### Еженедельный workflow

```bash
# 1. Создать недельный отчет
make rollup-weekly

# 2. Синхронизировать календарь
make calendar-push

# 3. Анализ кода
make code-analyze
```

### Управление проектом

```bash
# Поиск функций
./kira code search "def process_" --type function

# Информация о плагинах
./kira ext info kira-inbox --verbose

# Валидация системы
make validate
```

## Отладка и диагностика

### Подробный вывод

Большинство команд поддерживают флаг `--verbose`:

```bash
./kira inbox --verbose
./kira calendar pull --verbose
./kira rollup daily --verbose
```

### Dry-run режим

Команды, которые изменяют данные, поддерживают dry-run:

```bash
./kira inbox --dry-run
./kira calendar push --dry-run
```

### Проверка конфигурации

```bash
# Проверить зависимости
make check-deps

# Установить зависимости
make install-deps

# Тестирование CLI
make test-cli
```

## Интеграция с другими инструментами

### Makefile

Используйте Makefile для автоматизации:

```makefile
# В вашем Makefile
daily-report:
	make inbox
	make calendar-pull
	make rollup-daily

weekly-report:
	make rollup-weekly
	make calendar-push
```

### Cron

Настройте автоматическое выполнение:

```bash
# Crontab
0 9 * * * cd /path/to/kira && make inbox
0 18 * * * cd /path/to/kira && make rollup-daily
0 9 * * 1 cd /path/to/kira && make rollup-weekly
```

### CI/CD

Интегрируйте в pipeline:

```yaml
# GitHub Actions
- name: Validate Kira
  run: make validate

- name: Process Inbox
  run: make inbox
```

## Устранение неполадок

### Частые проблемы

1. **Модуль не найден**
   ```bash
   # Убедитесь, что вы в корне проекта
   cd /path/to/kira-project
   ./kira --help
   ```

2. **Конфигурация не загружается**
   ```bash
   # Проверьте наличие kira.yaml
   ls -la kira.yaml
   ```

3. **Расширения не работают**
   ```bash
   # Проверьте статус
   ./kira ext list --verbose
   ```

### Логи и отладка

```bash
# Включить подробный вывод
export KIRA_VERBOSE=1

# Запустить с отладкой
python3 -c "
import sys
sys.path.insert(0, 'src')
from kira.cli.kira_inbox import main
main(['--verbose'])
"
```

## Расширение CLI

### Добавление новых команд

1. Создайте модуль в `src/kira/cli/`
2. Добавьте функцию `main(args)`
3. Обновите `__main__.py`
4. Добавьте команду в Makefile

### Кастомные команды

```python
# src/kira/cli/kira_custom.py
def main(args):
    print("Моя кастомная команда")
    return 0
```

```bash
# Добавьте в Makefile
custom-command:
	./kira custom
```
