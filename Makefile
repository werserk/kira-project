# Makefile для Kira
# Упрощенные команды для работы с CLI

.PHONY: inbox calendar-pull calendar-push rollup-daily rollup-weekly validate ext-list help

# Показать справку
help:
	@echo "Доступные команды:"
	@echo "  inbox              - Запустить inbox-конвейер"
	@echo "  calendar-pull      - Синхронизировать календарь (pull)"
	@echo "  calendar-push      - Синхронизировать календарь (push)"
	@echo "  rollup-daily       - Создать дневной rollup"
	@echo "  rollup-weekly      - Создать недельный rollup"
	@echo "  validate           - Валидация Vault против схем"
	@echo "  ext-list           - Показать список расширений"
	@echo "  help               - Показать эту справку"

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
