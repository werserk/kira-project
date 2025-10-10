# Kira Makefile - Simple Docker workflow

.PHONY: help up down rebuild clean clean-all logs init

ENV ?= dev

help:  ## Show available commands
	@echo "🤖 Kira - Simple Commands:"
	@echo ""
	@echo "  make up         - Start Kira (Telegram + LangGraph + OpenRouter)"
	@echo "  make down       - Stop Kira"
	@echo "  make rebuild    - Rebuild and restart (no cache)"
	@echo "  make clean      - Remove containers and volumes (fast)"
	@echo "  make clean-all  - Deep clean including Docker cache (slow)"
	@echo "  make logs       - View logs"
	@echo ""
	@echo "⚙️  Configuration:"
	@echo "  Edit .env file to configure:"
	@echo "  - TELEGRAM_BOT_TOKEN"
	@echo "  - TELEGRAM_ALLOWED_CHAT_IDS"
	@echo "  - OPENROUTER_API_KEY (or ANTHROPIC_API_KEY)"
	@echo ""

init:  ## Initialize project (first time setup)
	@echo "🚀 Initializing Kira..."
	@mkdir -p vault/{tasks,notes,events,inbox,processed,projects,contacts,meetings,journal,resources,archive}
	@mkdir -p logs/{adapters,core,pipelines,plugins} artifacts/audit .rag tmp/telegram backups
	@touch vault/tasks/README.md vault/notes/README.md vault/inbox/README.md
	@if [ ! -f .env ]; then \
		cp config/env.example .env; \
		echo "📝 Created .env - please configure it with your tokens"; \
		echo ""; \
		echo "Required settings:"; \
		echo "  TELEGRAM_BOT_TOKEN=your_token"; \
		echo "  TELEGRAM_ALLOWED_CHAT_IDS=your_chat_id"; \
		echo "  OPENROUTER_API_KEY=your_key"; \
		echo ""; \
	else \
		echo "✓ .env already exists"; \
	fi
	@echo "✓ Kira initialized"

up:  ## Start Kira with Telegram + LangGraph + OpenRouter
	@if [ ! -f .env ]; then \
		echo "❌ Error: .env file not found"; \
		echo "Run: make init"; \
		exit 1; \
	fi
	@echo "🚀 Starting Kira..."
ifeq ($(ENV),dev)
	@docker compose -f compose.dev.yaml up -d
else
	@docker compose -f compose.yaml up -d
endif
	@echo "✅ Kira is running!"
	@echo ""
	@echo "📊 Status: make logs"
	@echo "🛑 Stop: make down"

down:  ## Stop Kira
	@echo "🛑 Stopping Kira..."
ifeq ($(ENV),dev)
	@docker compose -f compose.dev.yaml down
else
	@docker compose -f compose.yaml down
endif
	@echo "✅ Stopped"

rebuild:  ## Rebuild and restart (no cache)
	@echo "🔄 Rebuilding Kira (no cache)..."
	@make down
ifeq ($(ENV),dev)
	@docker compose -f compose.dev.yaml build --no-cache
	@docker compose -f compose.dev.yaml up -d
else
	@docker compose -f compose.yaml build --no-cache
	@docker compose -f compose.yaml up -d
endif
	@echo "✅ Rebuilt and restarted"

clean:  ## Remove all Docker containers and volumes
	@echo "🧹 Cleaning Kira Docker resources..."
ifeq ($(ENV),dev)
	@docker compose -f compose.dev.yaml down -v --remove-orphans 2>/dev/null || true
else
	@docker compose -f compose.yaml down -v --remove-orphans 2>/dev/null || true
endif
	@echo "✅ Cleaned"

clean-all:  ## Remove everything including Docker cache (slow)
	@echo "🧹 Deep cleaning (this may take a while)..."
	@make clean
	@echo "Pruning Docker system..."
	@docker system prune -f --volumes
	@echo "✅ Deep clean complete"

logs:  ## Follow logs in real-time
	@echo "📜 Following logs (Ctrl+C to stop)..."
ifeq ($(ENV),dev)
	@docker compose -f compose.dev.yaml logs -f
else
	@docker compose -f compose.yaml logs -f
endif
