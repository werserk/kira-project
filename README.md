# Kira

**Your Personal "Jarvis" for Obsidian**

Kira is an AI assistant that makes your Obsidian vault intelligent and self-managing. While Obsidian excels at viewing and editing, **Kira automates the hard parts**: task management, GTD workflows, Zettelkasten linking, and calendar sync.

**Primary Interface:** 💻 CLI + Telegram (Web UI available with configuration)
**Data Storage:** 📝 Standard Markdown (100% Obsidian-compatible)
**Intelligence:** 🤖 Multi-LLM AI (Anthropic, OpenAI, OpenRouter, Ollama)
**Deployment:** 🐳 **Docker-first** (everything runs in containers)

Think of it as: **Obsidian for viewing, Kira for doing.**

> ✨ **Fully Containerized:** All features run via Docker. No local Python installation needed!

---

## 🚀 Quick Start (< 5 minutes)

Get Kira running with just 3 commands:

```bash
# 1. Clone and initialize
git clone https://github.com/your-org/kira-project.git
cd kira-project
make init

# 2. Configure (edit .env with your API keys)
nano .env

# 3. Start everything
make quickstart
```

**That's it!** Kira is now running in Docker. 🎉

```bash
# Try it out:
make task-add TITLE="My first task"
make task-list
make today
```

**What you get:**
- ✅ Kira agent running in Docker
- ✅ Ollama for local AI (no API key needed)
- ✅ All CLI commands via `make`
- ✅ Telegram bot (if configured)
- ✅ Vault ready for Obsidian

---

## What is Kira?

**Kira = AI Assistant + Obsidian Compatibility**

Managing a personal knowledge system manually is exhausting. Zettelkasten requires discipline. GTD needs constant maintenance. Task management demands structure.

**Kira automates all of this.**

You interact with Kira through **Docker containers** (via Makefile commands or Telegram), and it:
- ✅ Creates and updates tasks with proper state management
- ✅ Maintains your Zettelkasten with bidirectional links
- ✅ Enforces GTD workflows automatically
- ✅ Syncs with your calendar
- ✅ Generates daily/weekly summaries
- ✅ Validates data integrity (so your vault never breaks)

Meanwhile, your notes live in **standard markdown format**, fully compatible with **Obsidian** for viewing and manual editing.

### The Problem Kira Solves

You love Obsidian's flexibility, but:
- 📝 **Manual maintenance is tedious** - Creating tasks, linking notes, updating states
- 🎯 **GTD requires discipline** - Easy to fall behind without automation
- 🔗 **Zettelkasten is hard** - Bidirectional linking and graph maintenance is mental overhead
- 🤖 **No intelligent assistant** - You do all the work manually
- ⏰ **Calendar sync is painful** - Keeping tasks and events in sync across tools
- 🔧 **Setup is complex** - Python environments, dependencies, configuration

**Kira solves this.** It's the AI layer that makes your Obsidian vault **intelligent and self-maintaining**, while you interact through simple Telegram messages or Docker commands.

### How It Works

```
┌───────────────────────────────────────────────────────────────┐
│                           YOU                                 │
└──────────────┬─────────────────────────────┬──────────────────┘
               │                             │
               │ Natural Language            │ Visual Interface
               │ (Telegram/Docker CLI)       │ (Manual Editing)
               ↓                             ↓
    ┌──────────────────────┐      ┌──────────────────────┐
    │   KIRA (Docker)      │      │   OBSIDIAN (UI)      │
    │                      │      │                      │
    │  • AI Processing     │      │  • Rich Editor       │
    │  • Task FSM          │      │  • Graph View        │
    │  • Validation        │      │  • Search            │
    │  • Auto-linking      │      │  • Plugins           │
    │  • Calendar Sync     │      │  • Themes            │
    │  • Reminders         │      │  • Visual Tools      │
    └──────────┬───────────┘      └──────────┬───────────┘
               │                             │
               │    Both read & write        │
               │    same markdown files      │
               │                             │
               └──────────┬──────────────────┘
                          ↓
              ┌────────────────────────┐
              │   VAULT (Markdown)     │
              │                        │
              │   • tasks/*.md         │
              │   • notes/*.md         │
              │   • projects/*.md      │
              │   • events/*.md        │
              │   • journal/*.md       │
              │                        │
              │   Standard markdown +  │
              │   YAML frontmatter     │
              └────────────────────────┘
```

**The Flow:**
1. **Via Docker (Makefile)**: You run `make task-add TITLE="Review Q4 report"`
   - Kira in Docker processes, validates, applies FSM rules
   - Writes `tasks/task-20251011-1420.md` to vault (mounted volume)

2. **Via Telegram**: You send *"Create task: Review Q4 report by Friday"*
   - Telegram bot in Docker processes with AI
   - Same result - creates task in vault

3. **Via Obsidian**: You manually create a note or edit existing task
   - Obsidian writes directly to vault as markdown
   - Kira sees the change and validates on next sync

4. **Result**: All tools work with the same files
   - Kira ensures structure, validation, automation
   - Obsidian provides beautiful UI and manual control
   - Your vault stays consistent and never corrupts

---

## 🐳 Docker-First Architecture

**Everything runs in containers. No local Python needed.**

### Available Services

```bash
# Check what's running
make status

# Expected output:
# kira-agent         Running (Telegram bot + AI)
# kira-ollama        Running (Local LLM)
```

### Common Commands

```bash
# Lifecycle
make up              # Start all services
make down            # Stop all services
make restart         # Restart services
make rebuild         # Rebuild and restart

# Monitoring
make logs            # View all logs
make logs-agent      # View Kira logs only
make status          # Show service status
make health          # Check API health

# Development
make shell           # Enter container shell
make dev             # Start with hot-reload
make prod            # Start in production mode

# CLI via Docker
make task-add TITLE="Task title"
make task-list
make today
make note-add TITLE="Note title"
make search QUERY="search term"

# Maintenance
make doctor          # Run diagnostics
make validate        # Check vault integrity
make test            # Run test suite
make backup          # Create backup
```

### Environment Modes

**Development Mode (default):**
```bash
make dev
# or
ENV=dev make up
```
- Hot-reload enabled
- Debug logging
- Telegram bot active
- Source code mounted for live changes

**Production Mode:**
```bash
make prod
# or
ENV=prod make up
```
- Optimized build
- HTTP API for agent
- Production logging
- Multi-stage Docker image

---

## 📦 Installation & Setup

### Prerequisites

- **Docker** 20.10+ and **Docker Compose** v2+
- **Git** for cloning the repository
- **Make** (usually pre-installed on Linux/Mac)
- **(Optional)** API keys for LLM providers

### Step-by-Step Setup

#### 1. Clone and Initialize

```bash
git clone https://github.com/your-org/kira-project.git
cd kira-project

# Initialize directories and create .env
make init
```

#### 2. Configure Environment

Edit `.env` file with your settings:

```bash
nano .env
```

**Minimal configuration (works out of the box):**
```bash
# LLM Provider (Ollama runs locally, no API key needed)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434

# Vault settings
KIRA_VAULT_PATH=/app/vault
KIRA_DEFAULT_TZ=UTC
```

**Optional: Add your API keys for better AI:**
```bash
# For cloud AI (choose one)
LLM_PROVIDER=openrouter  # or anthropic, openai
OPENROUTER_API_KEY=your-key-here
# ANTHROPIC_API_KEY=your-key-here
# OPENAI_API_KEY=your-key-here

# For Telegram integration
KIRA_TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your-bot-token-from-@BotFather

# For Google Calendar
KIRA_GCAL_ENABLED=true
GCAL_CREDENTIALS_PATH=./credentials.json
```

#### 3. Build and Start

```bash
# All-in-one command
make quickstart

# Or step by step:
make build           # Build Docker images
make up              # Start services
make logs            # Watch logs
```

#### 4. Verify Installation

```bash
# Check services are running
make status

# Run diagnostics
make doctor

# Create your first task
make task-add TITLE="Test task"
make task-list
```

**Expected output:**
```
✅ Vault structure: OK
✅ Configuration: OK
✅ LLM Provider: OK (ollama)
✅ Services: Running
```

---

## 🎯 Usage Examples

### Basic Task Management

```bash
# Create a task
make task-add TITLE="Review project documentation"

# List all tasks
make task-list

# See today's agenda
make today

# Enter shell for more commands
make shell
> kira task start task-20251009-1234
> kira task done task-20251009-1234
> kira task list --status doing
```

### Working with Notes

```bash
# Create a note
make note-add TITLE="Meeting insights"

# Search your vault
make search QUERY="project"

# Inside container shell
make shell
> kira note add "Key insight from meeting"
> kira links show note-20251009-1234
```

### Telegram Interface

Once configured, message your bot:

```
You: "Create task: Review PRs by Friday"
Kira: ✓ Created task-20251009-1420
      ✓ Due: 2025-10-11T17:00:00Z
      ✓ Added to calendar

You: "What's on my plate today?"
Kira: 📋 Tasks (3):
      • Review PRs (due 5pm) - HIGH
      • Team standup (10am)
      • Draft Q4 goals
```

### Daily Workflow

```bash
# Morning routine
make today                    # What's planned?

# Work on tasks (in shell)
make shell
> kira task start <task-id>
> kira task done <task-id>

# Evening review
make shell
> kira rollup daily          # Generate summary
```

### Advanced: Inside Container Shell

```bash
# Enter the container
make shell

# Full Kira CLI available:
kira task add "New task"
kira task list --status todo
kira note add "New note"
kira search "keyword"
kira validate
kira doctor
kira today
kira rollup daily

# Exit container
exit
```

---

## 🔧 Configuration

### LLM Providers

Choose one in `.env`:

**Option A: Ollama (Local, No API Key)**
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
```
✅ Privacy-first, runs locally
✅ No cost
⚠️ Requires more resources

**Option B: OpenRouter (Recommended)**
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key
```
✅ Access to multiple models
✅ Cost-effective

**Option C: Anthropic Claude**
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
```
✅ Best reasoning quality

**Option D: OpenAI**
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
```
✅ Widely available

### Telegram Setup

1. **Create bot with @BotFather:**
   ```
   /newbot
   # Follow prompts to get token
   ```

2. **Add to `.env`:**
   ```bash
   KIRA_TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=your-token
   ```

3. **Get your chat ID (optional whitelist):**
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   # Copy your chat.id
   ```

4. **Add to `.env`:**
   ```bash
   TELEGRAM_ALLOWED_CHAT_IDS=123456789
   ```

5. **Restart services:**
   ```bash
   make restart
   make logs-agent  # Watch for connection
   ```

### Google Calendar Setup

1. **Get OAuth credentials** from [Google Cloud Console](https://console.cloud.google.com/)
2. **Download `credentials.json`** to project root
3. **Enable in `.env`:**
   ```bash
   KIRA_GCAL_ENABLED=true
   GCAL_CREDENTIALS_PATH=./credentials.json
   ```
4. **Restart and authorize:**
   ```bash
   make restart
   make logs  # Follow OAuth flow in logs
   ```

---

## 🏗️ Architecture

### Docker Services

```yaml
services:
  kira-agent:           # Main Kira service (Telegram bot + AI)
    ports: 8000         # HTTP API (production mode)
    volumes:
      - vault/          # Your markdown files
      - logs/           # Application logs
      - artifacts/      # Agent states, audit

  ollama:               # Local LLM (optional)
    ports: 11434
    volumes:
      - ollama_data/    # Model storage
```

### Vault Structure

```
vault/
├── tasks/          # Todo items with FSM state management
├── notes/          # Free-form notes with bidirectional links
├── events/         # Calendar events with sync capabilities
├── projects/       # Project tracking with task hierarchy
├── contacts/       # People and relationships
├── meetings/       # Meeting notes with action items
├── journal/        # Daily reflections and logs
└── inbox/          # Unprocessed items requiring clarification
```

**Every entity has:**
- **Unique ID**: Collision-resistant, human-readable
- **Metadata**: Structured frontmatter with schema validation
- **Timestamps**: UTC-based, DST-aware
- **Links**: Bidirectional graph between entities
- **History**: Full audit log of changes

### Task State Machine

Tasks aren't just checkboxes—they have lifecycle management:

```
todo → doing → review → done
  ↓
blocked (with unblock conditions)
```

**Business Rules Enforced:**
- `todo → doing`: Requires assignee OR start time
- `doing → done`: Automatically sets completion timestamp
- `done → doing`: Requires reopen reason
- All transitions logged and validated before write

---

## 🔌 Plugin System

Extend Kira with custom logic without touching core code:

```python
from kira.plugin_sdk import decorators, PluginContext

@decorators.command("remind")
def set_reminder(context: PluginContext, task_id: str, hours: int):
    """Schedule a reminder for a task."""
    task = context.host_api.read_entity(task_id)
    # ... implement reminder logic
    context.logger.info(f"Reminder set for {task.title}")
```

**Built-in Plugins:**
- `kira-inbox`: Handles ambiguous inputs with clarification workflows
- `kira-calendar`: Syncs with Google Calendar (two-way)
- `kira-deadlines`: Proactive reminders for due dates
- `kira-rollup`: Generates daily/weekly summaries

Enable plugins in `.env`:
```bash
KIRA_ENABLE_PLUGINS=true
```

---

## 🧪 Testing & Diagnostics

### Run Tests in Container

```bash
# Full test suite
make test

# Unit tests only (fast)
make test-unit

# Integration tests
make test-integration
```

### System Diagnostics

```bash
# Health check
make doctor

# Validate vault integrity
make validate

# Check service health
make health

# View service status
make status
```

### Monitoring

```bash
# Watch all logs
make logs

# Agent logs only
make logs-agent

# Ollama logs
make logs-ollama

# Check running containers
make ps
```

---

## 🗄️ Backup & Restore

### Create Backup

```bash
# Create timestamped backup
make backup

# Output: backups/kira-backup-20251009-1234.tar.gz
```

**What's backed up:**
- `vault/` - All your markdown files
- `artifacts/` - Agent states and audit logs
- `logs/` - Application logs
- `.env` - Configuration (be careful with secrets!)

### Restore from Backup

```bash
make restore BACKUP=backups/kira-backup-20251009-1234.tar.gz
```

### Automated Backups

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * cd /path/to/kira-project && make backup
```

---

## 🎨 Obsidian Integration

Your vault is **100% Obsidian-compatible**!

### Setup

1. **Open Obsidian**
2. **File → Open Vault**
3. **Select `./vault` directory**

### What You Can Do

- 👁️ **View knowledge graph** - See all connections
- ✏️ **Edit tasks and notes** - Full manual control
- 🔍 **Use Obsidian search** - Powerful query capabilities
- 🔌 **Install plugins** - Dataview, Calendar, Graph View
- 🎨 **Customize themes** - Make it yours

### Markdown Example

```markdown
---
id: task-20251008-1420
title: Review Q4 report
status: todo
due: 2025-10-11T17:00:00Z
tags: [work, planning]
---

## Context
Need to review financial projections and team feedback.

Related: [[proj-q4-planning]], [[note-financial-model]]
```

**Kira maintains structure, Obsidian provides the viewing experience.**

---

## 🐛 Troubleshooting

### Services Not Starting

```bash
# Check Docker is running
docker ps

# Check compose file
make status

# Rebuild
make rebuild

# Check logs
make logs
```

### Permission Issues

```bash
# Fix vault permissions
chmod -R 755 vault/

# Restart
make restart
```

### API Key Issues

```bash
# Verify .env configuration
cat .env | grep API_KEY

# Test LLM connectivity
make doctor
```

### Container Issues

```bash
# Stop everything
make down

# Clean and restart
make clean
make build
make up

# Nuclear option (removes volumes)
make clean-all
make quickstart
```

### Telegram Bot Not Responding

```bash
# Check bot token
curl https://api.telegram.org/bot<TOKEN>/getMe

# View logs
make logs-agent

# Verify whitelist
cat .env | grep TELEGRAM_ALLOWED_CHAT_IDS
```

### Memory Issues (Ollama)

```bash
# Check resource usage
docker stats

# Limit Ollama memory (in compose.yaml)
services:
  ollama:
    deploy:
      resources:
        limits:
          memory: 4G
```

---

## 📊 Project Status

**Current Version:** `0.1.0-alpha`

**Maturity:**
- ✅ Core features stable (Vault, FSM, validation)
- ✅ Docker deployment production-ready
- ✅ CLI commands fully functional
- ✅ AI agent functional (multi-provider support)
- ⚙️ Telegram integration (requires configuration)
- ⚙️ Google Calendar sync (requires OAuth setup)

**Test Coverage:**
- 1169/1171 tests passing (99.8%)
- All features tested in containers

**What Works Out of the Box:**
- ✅ Docker deployment (everything containerized)
- ✅ All CLI commands via Makefile
- ✅ Vault operations (create, read, update, validate)
- ✅ Task FSM and validation
- ✅ Obsidian compatibility (100%)
- ✅ Ollama integration (local AI)

**What Requires Configuration:**
- ⚙️ **Cloud LLM**: API key for Anthropic/OpenAI/OpenRouter
- ⚙️ **Telegram Bot**: Token from @BotFather + whitelist
- ⚙️ **Google Calendar**: OAuth credentials

---

## 🗺️ Roadmap

### Phase 7 (Next Release)
- 🔄 Full two-way GCal sync with conflict resolution
- 📱 Mobile companion app (read-only)
- 🎨 Web UI for vault browsing
- ⚡ Performance optimization (indexing, caching)

### Phase 8 (Future)
- 🤝 Multi-user collaboration
- 🔐 End-to-end encryption
- 📊 Analytics dashboard
- 🌐 WebDAV/S3 sync for vault backup

### Long-Term Vision
- 🧠 Semantic search with vector embeddings
- 🔗 Integration marketplace (JIRA, GitHub, Slack)
- 🎯 Goal tracking with OKRs
- 📈 Predictive insights

---

## 💡 Why Docker-First?

**Benefits of Full Containerization:**

✅ **Zero Setup Hassles** - No Python version conflicts
✅ **Consistency** - Same environment everywhere
✅ **Isolation** - Doesn't interfere with your system
✅ **Portability** - Deploy anywhere Docker runs
✅ **Easy Updates** - `make rebuild` and you're done
✅ **Production-Ready** - Same setup for dev and prod

**Traditional problems solved:**
- ❌ "Works on my machine" - Not anymore!
- ❌ Python version conflicts - Isolated in container
- ❌ Dependency hell - Pre-built image
- ❌ Complex setup - Just `make quickstart`

---

## 📚 Additional Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Detailed setup guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - For developers
- **[CHANGELOG.md](CHANGELOG.md)** - Version history
- **[docs/architecture/](docs/architecture/)** - Architecture Decision Records (ADRs)
- **[examples/](examples/)** - Usage examples and demos

---

## 🤝 Contributing

Kira welcomes contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Code organization and architecture
- Testing requirements (95% coverage minimum)
- Docker development workflow
- Pull request process

**Quick Start for Contributors:**
```bash
git clone https://github.com/your-org/kira-project.git
cd kira-project
make init
make dev          # Start with hot-reload
make shell        # Enter container
> pytest tests/   # Run tests
```

---

## 🏆 Philosophy & Design Principles

### 1. **Docker-First**
Everything runs in containers. No local dependencies. Deploy anywhere.

### 2. **Obsidian Compatibility**
100% standard markdown. Use Obsidian for viewing. Kira for intelligence.

### 3. **Data Sovereignty**
Your data is yours. Local files. No cloud required. Obsidian-compatible always.

### 4. **Correctness Over Speed**
Every write is validated. Crashes can't corrupt state. Your vault stays clean.

### 5. **Automation Over Manual Work**
Let Kira handle structure, linking, validation. You focus on thinking.

---

## 📞 Contact & Support

For questions, issues, or feature requests:
- GitHub Issues: Report bugs and request features
- Documentation: Check `docs/` directory
- Community: Share your plugins and workflows

---

## 🎓 Technical Foundations

Kira's design is informed by:
- **GTD (Getting Things Done)** - David Allen's workflow methodology
- **Zettelkasten** - Niklas Luhmann's note-taking system
- **Local-first software** - Data ownership and offline-first
- **Container orchestration** - Modern DevOps practices
- **Production engineering** - Distributed systems patterns

Built with: **Docker**, **Python 3.12**, **FastAPI**, **Anthropic SDK**, **LangGraph**

---

**Enterprise-grade personal knowledge management for demanding professionals.**

*Version 0.1.0-alpha | Docker-First Edition | Last Updated: 2025-10-09*

---

© 2025 Kira Development Team. All rights reserved.
