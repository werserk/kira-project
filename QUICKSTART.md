# Quick Start Guide

**Get Kira running in under 15 minutes** ⏱️

This guide will help you set up Kira for the first time and create your first task.

---

## Prerequisites

- **Python 3.12+** installed
- **Poetry** for dependency management
- **(Optional)** API keys for LLM providers (Anthropic, OpenAI, or OpenRouter)
- **(Optional)** Telegram bot token (for Telegram interface)

---

## Step 1: Installation (5 minutes)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-org/kira-project.git
cd kira-project

# Install dependencies
poetry install

# Initialize vault structure
make init
```

**What this does:**
- Installs all required Python packages
- Creates vault folders: `tasks/`, `notes/`, `events/`, `inbox/`, etc.
- Sets up logging directories and audit trail

---

## Step 2: Configuration (5 minutes)

### Basic Configuration (CLI-only mode)

For CLI-only usage, you can start immediately:

```bash
# Create your first task right away!
poetry run kira task add "My first task"
poetry run kira task list
```

**✅ You're ready to use Kira via CLI!**

---

### Advanced Configuration (Optional - for AI Agent, Telegram, GCal)

If you want AI Agent, Telegram, or Google Calendar integration:

#### 2.1 Create Environment File

```bash
# Copy the example
cp config/env.example .env

# Edit with your favorite editor
nano .env  # or vim, code, etc.
```

#### 2.2 Configure LLM Provider (for AI Agent)

Choose one provider and add its API key to `.env`:

**Option A: OpenRouter (Recommended - Multi-model access)**
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-api-key-here
```

**Option B: Anthropic Claude**
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

**Option C: OpenAI**
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key-here
```

**Option D: Local Ollama (No API key needed)**
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
# Make sure Ollama is running: ollama serve
```

#### 2.3 Configure Telegram (Optional)

To use Telegram as your primary interface:

1. **Create a bot with [@BotFather](https://t.me/botfather)**:
   ```
   /newbot
   # Follow prompts to get your bot token
   ```

2. **Add to `.env`**:
   ```bash
   KIRA_TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=your-bot-token-here
   ```

3. **Get your chat ID** (optional whitelist):
   - Message your bot
   - Run: `curl https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Copy your `chat.id`
   - Add to `.env`: `TELEGRAM_ALLOWED_CHAT_IDS=your-chat-id`

#### 2.4 Configure Google Calendar (Optional)

For calendar sync:

1. **Get OAuth credentials** from [Google Cloud Console](https://console.cloud.google.com/):
   - Enable Google Calendar API
   - Create OAuth 2.0 credentials
   - Download `credentials.json`

2. **Add to `.env`**:
   ```bash
   KIRA_GCAL_ENABLED=true
   GCAL_CREDENTIALS_PATH=./credentials.json
   ```

#### 2.5 Enable Plugins (Optional)

```bash
KIRA_ENABLE_PLUGINS=true
```

---

## Step 3: First Run (5 minutes)

Choose your interface:

### Option A: CLI Mode (No setup required)

```bash
# Create a task
poetry run kira task add "Review project documentation"

# List tasks
poetry run kira task list

# Start working on a task
poetry run kira task start task-YYYYMMDD-HHMM

# Complete a task
poetry run kira task done task-YYYYMMDD-HHMM

# See today's agenda
poetry run kira today

# Validate your vault
poetry run kira validate
```

### Option B: AI Agent HTTP Service

```bash
# Start the agent service
poetry run kira agent start

# In another terminal, test it:
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a task: Buy groceries", "execute": false}'

# With execution:
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a task: Buy groceries", "execute": true}'
```

**Health check:**
```bash
curl http://localhost:8000/health
```

### Option C: Telegram Bot (Requires configuration from Step 2.3)

```bash
# Start Telegram bot with polling
poetry run kira telegram start --verbose

# Now message your bot:
# "Create a task: Finish quarterly report"
# The AI agent will process and respond!
```

### Option D: Docker Deployment

```bash
# Build and run with Docker Compose
make docker-build
make docker-up

# Agent will be available at http://localhost:8000
```

---

## Step 4: Verify Installation

### Run System Diagnostics

```bash
poetry run kira doctor
```

This checks:
- ✅ Vault structure
- ✅ Schema validation
- ✅ Configuration
- ✅ LLM provider connectivity (if configured)

### Run Tests (Optional)

```bash
# Quick smoke test
make smoke

# Full test suite
make test

# Unit tests only (fast)
make test-fast
```

---

## Common Workflows

### Daily Workflow

```bash
# Morning routine
kira today                    # What's on my plate?
kira task list --status todo  # Outstanding tasks

# Work on tasks
kira task start <task-id>
kira task done <task-id>

# Evening review
kira rollup daily             # Generate daily summary
```

### Working with Notes

```bash
# Create a note
kira note add "Meeting insights from Q4 planning"

# Search vault
kira search "Q4"

# View links
kira links show <entity-id>
```

### Calendar Integration (if configured)

```bash
# Pull events from Google Calendar
kira calendar pull

# Push tasks to calendar
kira calendar push

# View schedule
kira schedule view --today
```

### Telegram Workflow (if configured)

Message your bot:
- `"Create a task: Review PRs by Friday"`
- `"What tasks do I have today?"`
- `"Mark task-20251008-1234 as done"`
- `"Generate daily rollup"`

The AI agent understands natural language and executes commands!

---

## Next Steps

### 1. Customize Configuration

Edit `kira.yaml` for advanced settings:

```bash
cp config/kira.yaml.example kira.yaml
nano kira.yaml
```

Configure:
- Timezone
- Plugin settings
- Adapter preferences
- Feature flags

### 2. Learn More

- **Documentation**: See `README.md` for architecture overview
- **Examples**: Check `examples/demo_commands.md` for more usage patterns
- **Telegram Setup**: Read `docs/TELEGRAM_INTEGRATION.md` for advanced Telegram features
- **Adapters**: See `src/kira/adapters/README.md` for integration details

### 3. Obsidian Integration

Your vault is **100% Obsidian-compatible**!

```bash
# Open your vault in Obsidian
# File → Open Vault → Select ./vault directory
```

You can now:
- 👁️ View your knowledge graph
- ✏️ Manually edit tasks and notes
- 🔍 Use Obsidian's search and plugins
- 🎨 Customize with themes

**Kira maintains structure, Obsidian provides the perfect viewing experience.**

---

## Troubleshooting

### "Command not found: kira"

Use full Poetry path:
```bash
poetry run kira <command>
```

Or activate the virtual environment:
```bash
poetry shell
kira <command>
```

### "Vault not found"

Make sure you ran initialization:
```bash
make init
# OR
poetry run kira vault init
```

### "LLM provider error"

Check your `.env` file:
```bash
# Verify API key is set
cat .env | grep API_KEY

# Test provider connectivity
poetry run kira doctor
```

### "Telegram bot not responding"

1. Check bot token:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getMe
   ```

2. Check logs:
   ```bash
   tail -f logs/adapters/telegram.jsonl
   ```

3. Verify whitelist (if configured):
   ```bash
   # Make sure your chat_id is in TELEGRAM_ALLOWED_CHAT_IDS
   ```

### "Permission denied" errors

Check file permissions:
```bash
chmod +x scripts/*.sh
```

### Tests failing

```bash
# Run diagnostics first
make doctor

# Check specific test
poetry run pytest tests/unit/test_vault_storage.py -v
```

---

## What's Next?

### Using Kira Daily

1. **Morning**: `kira today` - See your agenda
2. **During work**: Use Telegram or CLI to capture tasks
3. **Evening**: `kira rollup daily` - Review what you accomplished

### Advanced Features

Once you're comfortable:
- **Plugins**: Extend functionality with custom plugins
- **Migration**: Import existing notes with `kira migrate run`
- **Backup**: Regular backups with `make backup`
- **Monitoring**: Watch logs with `kira monitor`

### Community

- Report issues on GitHub
- Share your plugins
- Contribute to documentation

---

## Quick Reference Card

```bash
# Task Management
kira task add "Title"              # Create task
kira task list                     # List all tasks
kira task start <id>               # Start working
kira task done <id>                # Complete task

# Information
kira today                         # Today's agenda
kira search "query"                # Search vault
kira stats                         # Personal analytics

# Maintenance
kira validate                      # Check integrity
kira doctor                        # System diagnostics
make backup                        # Backup vault

# Agent (if configured)
kira agent start                   # Start HTTP service
kira telegram start                # Start Telegram bot

# Calendar (if configured)
kira calendar pull                 # Import events
kira calendar push                 # Export tasks
```

---

**🎉 Congratulations!** You're now ready to use Kira as your personal AI assistant.

**Time to completion:** ~15 minutes ✅

For more details, see the full [README.md](README.md) and [documentation](docs/).
