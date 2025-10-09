# Kira Makefile - Docker-first workflow
# All commands run in containers for consistency and portability

.PHONY: help init build up down restart logs shell test doctor backup restore clean

# Default environment (production or dev)
ENV ?= dev

help:  ## Show this help message
	@echo "🤖 Kira - Docker-first commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "💡 Examples:"
	@echo "  make up              # Start all services"
	@echo "  make logs            # View logs"
	@echo "  make shell           # Enter container shell"
	@echo "  make task-add        # Create a task"
	@echo ""

# ============================================================================
# 🏗️  Docker Build & Lifecycle
# ============================================================================

init:  ## Initialize project (create directories and .env)
	@echo "🚀 Initializing Kira..."
	@mkdir -p vault/{tasks,notes,events,inbox,processed,projects,contacts,meetings,journal,resources,archive}
	@mkdir -p logs artifacts/audit .rag tmp/telegram backups
	@touch vault/tasks/README.md vault/notes/README.md vault/inbox/README.md vault/processed/README.md vault/projects/README.md
	@if [ ! -f .env ]; then cp config/env.example .env && echo "📝 Created .env file - please configure it"; fi
	@echo "✓ Kira initialized"
	@echo "➡️  Next: Configure .env and run 'make up'"

build:  ## Build Docker images
	@echo "🔨 Building Docker images..."
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml build
else
	docker compose -f compose.yaml build
endif
	@echo "✓ Build complete"

up:  ## Start all services in background
	@echo "🚀 Starting Kira services..."
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml up -d
else
	docker compose -f compose.yaml up -d
endif
	@echo "✓ Services started"
	@echo "📊 Check status: make status"
	@echo "📜 View logs: make logs"

down:  ## Stop all services
	@echo "🛑 Stopping Kira services..."
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml down
else
	docker compose -f compose.yaml down
endif
	@echo "✓ Services stopped"

restart:  ## Restart all services
	@make down
	@make up

status:  ## Show service status
	@echo "📊 Service Status:"
ifeq ($(ENV),dev)
	@docker compose -f compose.dev.yaml ps
else
	@docker compose -f compose.yaml ps
endif

logs:  ## Follow logs from all services
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml logs -f
else
	docker compose -f compose.yaml logs -f
endif

logs-agent:  ## Follow logs from Kira agent only
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml logs -f kira-telegram-bot
else
	docker compose -f compose.yaml logs -f kira-agent
endif

logs-ollama:  ## Follow logs from Ollama only
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml logs -f ollama
else
	docker compose -f compose.yaml logs -f ollama
endif

# ============================================================================
# 🐚 Shell Access
# ============================================================================

shell:  ## Open shell in Kira container
	@echo "🐚 Opening shell in Kira container..."
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot /bin/bash
else
	docker compose -f compose.yaml exec kira-agent /bin/bash
endif

shell-root:  ## Open root shell in Kira container
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec -u root kira-telegram-bot /bin/bash
else
	docker compose -f compose.yaml exec -u root kira-agent /bin/bash
endif

# ============================================================================
# 🧪 Testing & Diagnostics
# ============================================================================

test:  ## Run full test suite in container
	@echo "🧪 Running tests in container..."
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run pytest tests/ -v
else
	docker compose -f compose.yaml exec kira-agent poetry run pytest tests/ -v
endif

test-unit:  ## Run unit tests only
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run pytest tests/unit/ -v
else
	docker compose -f compose.yaml exec kira-agent poetry run pytest tests/unit/ -v
endif

test-integration:  ## Run integration tests only
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run pytest tests/integration/ -v
else
	docker compose -f compose.yaml exec kira-agent poetry run pytest tests/integration/ -v
endif

doctor:  ## Run system diagnostics in container
	@echo "🏥 Running diagnostics..."
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run kira doctor
else
	docker compose -f compose.yaml exec kira-agent poetry run kira doctor
endif

validate:  ## Validate vault integrity
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run kira validate
else
	docker compose -f compose.yaml exec kira-agent poetry run kira validate
endif

# ============================================================================
# 📋 CLI Commands via Docker
# ============================================================================

task-add:  ## Add a task (usage: make task-add TITLE="Task title")
	@if [ -z "$(TITLE)" ]; then \
		echo "❌ Error: Please specify TITLE=\"Your task title\""; \
		exit 1; \
	fi
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run kira task add "$(TITLE)"
else
	docker compose -f compose.yaml exec kira-agent poetry run kira task add "$(TITLE)"
endif

task-list:  ## List all tasks
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run kira task list
else
	docker compose -f compose.yaml exec kira-agent poetry run kira task list
endif

today:  ## Show today's agenda
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run kira today
else
	docker compose -f compose.yaml exec kira-agent poetry run kira today
endif

note-add:  ## Add a note (usage: make note-add TITLE="Note title")
	@if [ -z "$(TITLE)" ]; then \
		echo "❌ Error: Please specify TITLE=\"Your note title\""; \
		exit 1; \
	fi
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run kira note add "$(TITLE)"
else
	docker compose -f compose.yaml exec kira-agent poetry run kira note add "$(TITLE)"
endif

search:  ## Search vault (usage: make search QUERY="search term")
	@if [ -z "$(QUERY)" ]; then \
		echo "❌ Error: Please specify QUERY=\"search term\""; \
		exit 1; \
	fi
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run kira search "$(QUERY)"
else
	docker compose -f compose.yaml exec kira-agent poetry run kira search "$(QUERY)"
endif

# ============================================================================
# 🗄️  Backup & Restore
# ============================================================================

backup:  ## Create backup of vault and logs
	@echo "💾 Creating backup..."
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d-%H%M%S); \
	tar -czf backups/kira-backup-$$TIMESTAMP.tar.gz vault/ artifacts/ logs/ config/ .env 2>/dev/null || true
	@echo "✓ Backup created in backups/"

restore:  ## Restore from backup (usage: make restore BACKUP=path/to/backup.tar.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "❌ Error: Please specify BACKUP=path/to/backup.tar.gz"; \
		exit 1; \
	fi
	@echo "📦 Restoring from $(BACKUP)..."
	@tar -xzf $(BACKUP)
	@echo "✓ Restored from backup"

# ============================================================================
# 🧹 Cleanup
# ============================================================================

clean:  ## Clean temporary files (keeps volumes)
	@echo "🧹 Cleaning temporary files..."
	@rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned"

clean-all:  ## Clean everything including Docker volumes
	@echo "🧹 Cleaning all (including Docker volumes)..."
	@make down
ifeq ($(ENV),dev)
	docker compose -f compose.dev.yaml down -v
else
	docker compose -f compose.yaml down -v
endif
	@make clean
	@echo "✓ All cleaned"

prune:  ## Remove unused Docker resources
	@echo "🗑️  Pruning Docker resources..."
	docker system prune -f
	@echo "✓ Pruned"

# ============================================================================
# 🔧 Development Helpers
# ============================================================================

dev:  ## Start in development mode with hot-reload
	@echo "🔥 Starting in development mode..."
	@ENV=dev make up
	@echo "💡 Code changes will hot-reload automatically"

prod:  ## Start in production mode
	@echo "🚀 Starting in production mode..."
	@ENV=prod make up

rebuild:  ## Rebuild and restart (useful after dependency changes)
	@echo "🔄 Rebuilding and restarting..."
	@make down
	@make build
	@make up

# ============================================================================
# 📚 Documentation & Info
# ============================================================================

health:  ## Check health of services
	@echo "🏥 Checking service health..."
	@curl -s http://localhost:8000/health | jq . || echo "⚠️  Agent service not responding"

version:  ## Show Kira version
ifeq ($(ENV),dev)
	@docker compose -f compose.dev.yaml exec kira-telegram-bot poetry run kira --version
else
	@docker compose -f compose.yaml exec kira-agent poetry run kira --version
endif

ps:  ## Show running containers
	@docker ps --filter "name=kira"

# ============================================================================
# 🎯 Quick Start
# ============================================================================

quickstart:  ## Complete setup: init → build → up
	@echo "🎯 Quick Start: Full setup"
	@make init
	@make build
	@make up
	@echo ""
	@echo "✅ Kira is ready!"
	@echo "📝 Edit .env to configure API keys"
	@echo "💡 Try: make task-add TITLE=\"My first task\""
	@echo "📊 View logs: make logs"
