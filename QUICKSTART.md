# Quick Start Guide - Docker Edition

**Get Kira running in under 5 minutes** ⏱️

This guide will help you set up Kira using Docker - no Python installation required!

---

## Prerequisites

- **Docker** 20.10+ and **Docker Compose** v2+
- **Git** for cloning the repository
- **Make** (usually pre-installed on Linux/Mac, available via Chocolatey on Windows)
- **(Optional)** API keys for LLM providers (or use Ollama for free local AI)

---

## Step 1: Installation (2 minutes)

### Clone and Initialize

```bash
# Clone the repository
git clone https://github.com/your-org/kira-project.git
cd kira-project

# Initialize directories and create .env template
make init
```

**What this does:**
- Creates vault folders: `tasks/`, `notes/`, `events/`, `inbox/`, etc.
- Sets up logging directories and audit trail
- Creates `.env` file from template

---

## Step 2: Configuration (2 minutes)

Edit the `.env` file with your settings:

```bash
nano .env  # or use your favorite editor
```

### Minimal Configuration (Works Out of the Box)

```bash
# LLM Provider - Ollama runs locally, no API key needed
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434

# Vault settings
KIRA_VAULT_PATH=/app/vault
KIRA_DEFAULT_TZ=UTC
```

**This configuration works immediately with free local AI!** ✅

### Optional: Enhanced Configuration

#### Add Cloud AI (Better Quality)

Choose one:

```bash
# OpenRouter (Recommended - access to multiple models)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key-here

# OR Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key-here

# OR OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key-here
```

#### Add Telegram Integration

```bash
KIRA_TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your-bot-token-from-@BotFather
TELEGRAM_ALLOWED_CHAT_IDS=your-chat-id  # Optional whitelist
```

**How to get Telegram bot token:**
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot`
3. Follow prompts to get your token

#### Add Google Calendar Sync

```bash
KIRA_GCAL_ENABLED=true
GCAL_CREDENTIALS_PATH=./credentials.json
```

---

## Step 3: Start Kira (1 minute)

### Quick Start (All-in-One)

```bash
make quickstart
```

This will:
1. ✅ Build Docker images
2. ✅ Start all services
3. ✅ Show you next steps

### Or Step by Step

```bash
# Build Docker images
make build

# Start services in background
make up

# View logs (Ctrl+C to stop viewing)
make logs
```

**That's it! Kira is now running.** 🎉

---

## Step 4: Verify Installation

### Check Service Status

```bash
make status
```

Expected output:
```
📊 Service Status:
NAME                  IMAGE              STATUS         PORTS
kira-telegram-dev     kira-dev:latest    Up 2 minutes
kira-ollama-dev      ollama/ollama      Up 2 minutes   0.0.0.0:11434->11434/tcp
```

### Run System Diagnostics

```bash
make doctor
```

Expected output:
```
✅ Vault structure: OK
✅ Configuration: OK
✅ LLM Provider: OK (ollama)
✅ Docker services: Running
```

---

## Step 5: Try It Out!

### Create Your First Task

```bash
make task-add TITLE="My first task"
```

Output:
```
✓ Created task-20251009-1234
```

### List All Tasks

```bash
make task-list
```

### See Today's Agenda

```bash
make today
```

### More CLI Commands

```bash
# Create a note
make note-add TITLE="Important meeting notes"

# Search your vault
make search QUERY="meeting"

# View all available commands
make help
```

---

## Using Kira

### Option A: Makefile Commands (Recommended)

Quick access to common operations:

```bash
# Task management
make task-add TITLE="Review code"
make task-list
make today

# Notes
make note-add TITLE="New idea"

# Search
make search QUERY="keyword"

# Monitoring
make logs           # View all logs
make status         # Check services
make doctor         # Run diagnostics
```

### Option B: Inside Container Shell

For full CLI access:

```bash
# Enter the container
make shell

# Now you have full Kira CLI:
kira task add "New task"
kira task list --status todo
kira task start task-20251009-1234
kira task done task-20251009-1234
kira note add "New note"
kira search "keyword"
kira validate
kira today
kira rollup daily

# Exit container
exit
```

### Option C: Telegram Interface

If you configured Telegram bot:

```
You: "Create task: Buy groceries"
Kira: ✓ Created task-20251009-1420

You: "What's on my plate today?"
Kira: 📋 Tasks (2):
      • Buy groceries
      • Review code

You: "Mark task-20251009-1420 as done"
Kira: ✓ Task completed
```

---

## Common Workflows

### Daily Workflow

```bash
# Morning routine
make today                    # What's planned?

# Work on tasks (enter shell)
make shell
> kira task start <task-id>
> kira task done <task-id>

# Evening review
> kira rollup daily          # Generate summary
> exit
```

### Development Mode

For active development with hot-reload:

```bash
# Start in dev mode (default)
make dev

# Make changes to code in src/kira/
# Changes will automatically reload!

# View logs
make logs-agent
```

### Production Mode

For stable deployment:

```bash
# Start in production mode
make prod

# API available at http://localhost:8000
curl http://localhost:8000/health
```

---

## Obsidian Integration

Your vault is **100% Obsidian-compatible**!

### Setup

1. **Open Obsidian**
2. **File → Open Vault**
3. **Select `./vault` directory** in your kira-project folder

### What You Can Do

- 👁️ **View knowledge graph** - See all task/note connections
- ✏️ **Edit tasks and notes** - Full manual control
- 🔍 **Use Obsidian search** - Powerful queries
- 🔌 **Install plugins** - Dataview, Calendar, Graph View
- 🎨 **Customize themes** - Make it yours

**Kira maintains structure, Obsidian provides the viewing experience.**

---

## Docker Management

### Service Control

```bash
make up              # Start services
make down            # Stop services
make restart         # Restart services
make status          # Check status
```

### Logs & Monitoring

```bash
make logs            # All logs
make logs-agent      # Kira agent only
make logs-ollama     # Ollama only
make ps              # Running containers
```

### Development

```bash
make dev             # Start with hot-reload
make shell           # Enter container shell
make shell-root      # Root shell (for debugging)
make rebuild         # Rebuild after dependency changes
```

### Testing

```bash
make test            # Full test suite
make test-unit       # Unit tests only
make test-integration # Integration tests
make validate        # Validate vault
make doctor          # System diagnostics
```

### Cleanup

```bash
make clean           # Clean temp files
make clean-all       # Clean everything including volumes
make prune           # Remove unused Docker resources
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check Docker is running
docker ps

# View detailed logs
make logs

# Rebuild from scratch
make rebuild
```

### Port Already in Use

If port 8000 or 11434 is already in use:

Edit `compose.yaml` or `compose.dev.yaml`:
```yaml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

Then:
```bash
make restart
```

### Permission Issues

```bash
# Fix vault permissions
chmod -R 755 vault/ logs/ artifacts/

# Restart
make restart
```

### Out of Memory (Ollama)

Adjust resource limits in `compose.dev.yaml`:
```yaml
services:
  ollama:
    deploy:
      resources:
        limits:
          memory: 4G  # Reduce from 8G
```

Then:
```bash
make rebuild
```

### Telegram Bot Not Responding

```bash
# Check bot token
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# View bot logs
make logs-agent

# Verify .env configuration
cat .env | grep TELEGRAM
```

### Clean Install

If everything is broken:

```bash
# Nuclear option: clean everything
make clean-all

# Start fresh
make init
nano .env           # Reconfigure
make quickstart
```

---

## Backup & Restore

### Create Backup

```bash
make backup
```

Creates: `backups/kira-backup-YYYYMMDD-HHMMSS.tar.gz`

**What's backed up:**
- All vault files (tasks, notes, etc.)
- Artifacts and audit logs
- Application logs
- Configuration (.env)

### Restore from Backup

```bash
make restore BACKUP=backups/kira-backup-20251009-1234.tar.gz
```

### Automated Backups

Add to crontab:
```bash
crontab -e

# Add this line for daily backups at 2 AM:
0 2 * * * cd /path/to/kira-project && make backup
```

---

## Next Steps

### 1. Explore Kira Features

```bash
# View all commands
make help

# Enter shell for full CLI
make shell
> kira --help
```

### 2. Customize Configuration

Edit `kira.yaml` for advanced settings:
```bash
cp config/kira.yaml.example kira.yaml
nano kira.yaml
```

Configure:
- Timezone preferences
- Plugin settings
- Feature flags
- Adapter preferences

### 3. Learn More

- **Main README**: [README.md](README.md) - Full documentation
- **Architecture**: [docs/architecture/](docs/architecture/) - Design decisions
- **Examples**: [examples/demo_commands.md](examples/demo_commands.md) - Usage patterns
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md) - For developers

### 4. Enable Advanced Features

**Plugins:**
```bash
# In .env:
KIRA_ENABLE_PLUGINS=true

# Restart:
make restart
```

**RAG (Knowledge Base Search):**
```bash
# In .env:
ENABLE_RAG=true

# Build index:
make shell
> kira rag build

# Restart:
exit
make restart
```

---

## Common Questions

### Do I need to install Python?

**No!** Everything runs in Docker. No local Python installation needed.

### Which LLM provider should I use?

- **Ollama** (free, local) - Good for privacy, requires more resources
- **OpenRouter** (paid) - Best value, multiple models
- **Anthropic** (paid) - Best reasoning quality
- **OpenAI** (paid) - Widely available

Start with Ollama for free, upgrade to cloud later if needed.

### Can I use Kira without Telegram?

**Yes!** Use Makefile commands or container shell:
```bash
make task-add TITLE="Task"
make shell
> kira task list
```

### How do I update Kira?

```bash
git pull origin main
make rebuild
```

### Is my data safe?

Yes! All data is stored locally in `vault/` as plain markdown files. No cloud dependency (unless you choose cloud LLM).

### Can I use this in production?

Yes! Use production mode:
```bash
make prod
```

Resource limits and health checks are configured.

---

## Quick Reference Card

```bash
# Setup
make init               # Initialize project
make build              # Build images
make up                 # Start services

# Daily Use
make task-add TITLE="Task"
make task-list
make today
make shell              # Full CLI access

# Monitoring
make status             # Service status
make logs               # View logs
make doctor             # Diagnostics

# Maintenance
make backup             # Backup vault
make restart            # Restart services
make clean              # Clean temp files

# Help
make help               # Show all commands
```

---

## Environment Cheat Sheet

### Development Mode (Default)

```bash
make dev               # or just 'make up'
```

- Hot-reload enabled
- Debug logging
- Telegram bot active
- Changes to `src/` reload automatically

### Production Mode

```bash
make prod
```

- Optimized build
- HTTP API on port 8000
- Production logging
- No hot-reload

### Switch Modes

```bash
make down
ENV=prod make up       # Switch to production
ENV=dev make up        # Switch to development
```

---

**🎉 Congratulations!** You're now ready to use Kira.

**Time to completion:** ~5 minutes ✅

Everything runs in Docker - consistent, isolated, and portable.

For more details, see the full [README.md](README.md).

---

*Version 0.1.0-alpha | Docker-First Edition | Last Updated: 2025-10-09*
