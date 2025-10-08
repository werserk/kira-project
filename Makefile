# Kira Makefile - Common development and operations tasks

.PHONY: help init smoke test backup restore docker-build docker-up

help:  ## Show this help message
	@echo "Kira - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

init:  ## Initialize project (install deps, create vault)
	@echo "Initializing Kira..."
	poetry install
	mkdir -p vault/{tasks,notes,events,inbox,processed,projects,contacts,meetings,journal,resources,archive}
	mkdir -p logs artifacts/audit .rag
	touch vault/tasks/README.md vault/notes/README.md vault/inbox/README.md
	@echo "✓ Kira initialized"

smoke:  ## Run smoke tests
	poetry run python -m pytest tests/unit/test_agent_tools.py -v -k "test_execute_dry_run"

test:  ## Run full test suite
	poetry run python -m pytest tests/ -v

test-fast:  ## Run fast unit tests only
	poetry run python -m pytest tests/unit/ -v

doctor:  ## Run system diagnostics
	poetry run python -m kira.cli doctor

monitor:  ## Monitor live logs
	poetry run python -m kira.cli monitor

backup:  ## Create backup of vault and audit logs
	@echo "Creating backup..."
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d-%H%M%S); \
	tar -czf backups/kira-backup-$$TIMESTAMP.tar.gz vault/ artifacts/ logs/ config/ .env 2>/dev/null || true
	@echo "✓ Backup created in backups/"

restore:  ## Restore from backup (usage: make restore BACKUP=path/to/backup.tar.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "Error: Please specify BACKUP=path/to/backup.tar.gz"; \
		exit 1; \
	fi
	@echo "Restoring from $(BACKUP)..."
	@tar -xzf $(BACKUP)
	@echo "✓ Restored from backup"

clean:  ## Clean temporary files
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name  "__pycache__" -exec rm -rf {} + 2>/dev/null || true

docker-build:  ## Build Docker image
	docker build -t kira-agent:latest .

docker-up:  ## Start services with Docker Compose
	docker compose up -d

docker-down:  ## Stop Docker Compose services
	docker compose down

rag-build:  ## Build RAG index from documentation
	@echo "Building RAG index..."
	@poetry run python -c "from pathlib import Path; from kira.agent.rag import build_rag_index; build_rag_index(Path('vault'), Path('.rag/index.json'))"
	@echo "✓ RAG index built"

rollup-daily:  ## Generate daily rollup
	poetry run python -m kira.cli rollup daily

rollup-weekly:  ## Generate weekly rollup
	poetry run python -m kira.cli rollup weekly
