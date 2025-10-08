# Makefile для Kira
# Упрощенные команды для работы с CLI

.PHONY: inbox calendar-pull calendar-push rollup-daily rollup-weekly validate ext-list vault-init vault-validate vault-info help init smoke rollup:daily rollup:weekly backup restore

# Показать справку
help:
	@echo "Доступные команды:"
	@echo "  init               - Полная инициализация (создание vault, установка зависимостей)"
	@echo "  smoke              - Smoke-тест (создание/обновление/получение задачи)"
	@echo "  backup             - Создать резервную копию vault"
	@echo "  restore            - Восстановить vault из резервной копии"
	@echo "  inbox              - Запустить inbox-конвейер"
	@echo "  calendar-pull      - Синхронизировать календарь (pull)"
	@echo "  calendar-push      - Синхронизировать календарь (push)"
	@echo "  rollup:daily       - Создать дневной rollup"
	@echo "  rollup:weekly      - Создать недельный rollup"
	@echo "  vault-init         - Инициализировать Vault"
	@echo "  vault-validate     - Валидировать Vault структуру"
	@echo "  vault-info         - Показать информацию о Vault"
	@echo "  validate           - Валидация Vault против схем"
	@echo "  ext-list           - Показать список расширений"
	@echo "  help               - Показать эту справку"

# Phase 6: Инициализация и smoke-тесты
init:
	@echo "🚀 Инициализация Kira..."
	@echo "1️⃣  Проверка зависимостей..."
	@command -v poetry >/dev/null 2>&1 || { echo "❌ Poetry не установлен. Установите: pip install poetry"; exit 1; }
	@echo "2️⃣  Установка зависимостей..."
	@poetry install --no-interaction
	@echo "3️⃣  Создание конфигурации..."
	@if [ ! -f .env ]; then cp config/env.example .env && echo "✅ Создан .env файл"; else echo "⏭️  .env уже существует"; fi
	@if [ ! -f kira.yaml ]; then cp config/kira.yaml.example kira.yaml && echo "✅ Создан kira.yaml"; else echo "⏭️  kira.yaml уже существует"; fi
	@echo "4️⃣  Инициализация vault..."
	@poetry run python -m kira.cli vault init || echo "⏭️  Vault уже инициализирован"
	@echo "✅ Kira инициализирован успешно!"

smoke:
	@echo "🧪 Запуск smoke-теста..."
	@echo "1️⃣  Создание тестовой задачи..."
	@TASK_ID=$$(poetry run python -m kira.cli task add "Smoke test task" --status todo --json 2>/dev/null | grep -o '"uid":"[^"]*"' | cut -d'"' -f4); \
	if [ -z "$$TASK_ID" ]; then \
		TASK_ID=$$(poetry run python -m kira.cli task add "Smoke test task" --status todo 2>&1 | grep -o 'task-[a-z0-9-]*' | head -1); \
	fi; \
	if [ -z "$$TASK_ID" ]; then \
		echo "❌ Не удалось создать задачу"; \
		exit 1; \
	fi; \
	echo "✅ Задача создана: $$TASK_ID"; \
	echo "2️⃣  Обновление задачи..."; \
	poetry run python -m kira.cli task update $$TASK_ID --status doing --assignee "smoke-test" >/dev/null 2>&1 || \
	poetry run python -m kira.cli task start $$TASK_ID >/dev/null 2>&1; \
	echo "✅ Задача обновлена"; \
	echo "3️⃣  Получение задачи..."; \
	poetry run python -m kira.cli task list --limit 5 >/dev/null 2>&1; \
	echo "✅ Задача получена"; \
	echo "✅ Smoke-тест завершен успешно!"

# Rollup команды (aliases для совместимости с Phase 6)
rollup:daily:
	@$(MAKE) rollup-daily

rollup:weekly:
	@$(MAKE) rollup-weekly

# Inbox команды
inbox:
	./kira inbox

inbox-verbose:
	./kira inbox --verbose

inbox-dry-run:
	./kira inbox --dry-run --verbose

# Calendar команды
calendar-pull:
	./kira calendar pull

calendar-push:
	./kira calendar push

calendar-pull-verbose:
	./kira calendar pull --verbose

calendar-push-verbose:
	./kira calendar push --verbose

calendar-push-dry-run:
	./kira calendar push --dry-run --verbose

# Rollup команды
rollup-daily:
	./kira rollup daily

rollup-weekly:
	./kira rollup weekly

rollup-daily-verbose:
	./kira rollup daily --verbose

rollup-weekly-verbose:
	./kira rollup weekly --verbose

rollup-daily-custom:
	./kira rollup daily --date $(DATE) --verbose

rollup-weekly-custom:
	./kira rollup weekly --week $(WEEK) --verbose

# Code команды
code-analyze:
	./kira code analyze --verbose

code-index:
	./kira code index --verbose

code-search:
	./kira code search "$(QUERY)" --verbose

# Vault команды
vault-init:
	./kira vault init --verbose

vault-validate:
	./kira vault validate --verbose

vault-info:
	./kira vault info --verbose

vault-schemas:
	./kira vault schemas --list --verbose

vault-new-task:
	./kira vault new --type task --title "$(TITLE)" --verbose

vault-new-note:
	./kira vault new --type note --title "$(TITLE)" --verbose

# Backup & Restore команды (Phase 6)
backup:
	@./scripts/backup_vault.sh .

restore:
	@if [ -z "$(FILE)" ]; then \
		echo "❌ Укажите файл бэкапа: make restore FILE=vault-backup-20251008.tar.gz"; \
		exit 1; \
	fi; \
	./scripts/restore_vault.sh "$(FILE)"

# Ext команды
ext-list:
	./kira ext list

ext-list-verbose:
	./kira ext list --verbose

ext-enable:
	./kira ext enable $(NAME)

ext-disable:
	./kira ext disable $(NAME)

ext-info:
	./kira ext info $(NAME) --verbose

# Валидация
validate:
	python3 test_cli.py

# Полная валидация с использованием yq (если установлен)
validate-full:
	@if command -v yq >/dev/null 2>&1; then \
		python3 -m kira.core.schemas --validate $$(yq '.vault.path' kira.yaml); \
	else \
		echo "yq не установлен, используем стандартную валидацию"; \
		python3 test_cli.py; \
	fi

# Утилиты
check-deps:
	@echo "Проверка зависимостей..."
	@python -c "import yaml, jsonschema; print('✅ Основные зависимости установлены')" || echo "❌ Не все зависимости установлены"

install-deps:
	@echo "Установка зависимостей..."
	pip install pyyaml jsonschema

# Тестирование
test-cli:
	@echo "Тестирование CLI команд..."
	python -m kira.cli ext list
	python3 test_cli.py

# Очистка
clean:
	@echo "Очистка временных файлов..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# Примеры использования
examples:
	@echo "Примеры использования:"
	@echo ""
	@echo "1. Обработка inbox:"
	@echo "   make inbox"
	@echo ""
	@echo "2. Синхронизация календаря:"
	@echo "   make calendar-pull"
	@echo "   make calendar-push"
	@echo ""
	@echo "3. Создание rollup отчетов:"
	@echo "   make rollup-daily"
	@echo "   make rollup-weekly"
	@echo ""
	@echo "4. Управление расширениями:"
	@echo "   make ext-list"
	@echo "   make ext-enable NAME=kira-calendar"
	@echo "   make ext-disable NAME=kira-calendar"
	@echo ""
	@echo "5. Валидация:"
	@echo "   make validate"
	@echo ""
	@echo "6. Работа с кодом:"
	@echo "   make code-analyze"
	@echo "   make code-search QUERY='function_name'"
	@echo ""
	@echo "7. Управление Vault:"
	@echo "   make vault-init"
	@echo "   make vault-validate"
	@echo "   make vault-info"
	@echo "   make vault-new-task TITLE='My Task'"
	@echo "   make vault-new-note TITLE='My Note'"
