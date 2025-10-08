# Kira - Personal Knowledge & Task Management System

**Intelligent personal assistant for managing tasks, notes, events, and knowledge**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/poetry-managed-blue)](https://python-poetry.org/)
[![ADR Implementation](https://img.shields.io/badge/ADR-100%25-success)](docs/adr/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Type Checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue)](http://mypy-lang.org/)

---

## 🎯 What is Kira?

Kira is a **markdown-based personal knowledge management system** that helps you:

- 📥 **Capture** - Collect tasks and notes from multiple sources (Telegram, CLI, files)
- 🧹 **Organize** - Automatically normalize and categorize your items
- 🔗 **Connect** - Build a knowledge graph with bidirectional links
- 📊 **Review** - Generate daily/weekly rollups and reports
- 📅 **Sync** - Two-way sync with Google Calendar
- ✅ **Execute** - Track task lifecycle with FSM (todo→doing→done)
- 🔍 **Validate** - Ensure data integrity with schema validation

### Key Features

- **Markdown-First**: All data stored as human-readable `.md` files
- **Plugin Architecture**: Extensible via stable SDK
- **Event-Driven**: Loosely coupled components via event bus
- **Type-Safe**: Full Python type annotations and validation
- **CLI-Native**: Powerful command-line interface
- **Git-Friendly**: Plain text files, easy to version control
- **Security-First**: Subprocess sandboxing for plugins

---

## ⚡ Quick Start

### 5-Minute Setup

```bash
# Clone repository
git clone <repository-url> kira-project
cd kira-project

# Install
poetry install

# Activate environment
poetry shell

# Initialize Vault
cp config/kira.yaml.example kira.yaml
kira vault init

# Create first task
kira vault new --type task --title "Learn Kira"

# Verify
kira validate
ls vault/tasks/
```

**✅ Done! You're ready to use Kira.**

👉 **Full setup guide:** [QUICKSTART.md](QUICKSTART.md)

---

## 📚 Documentation

### Getting Started
- 🚀 [**QUICKSTART.md**](QUICKSTART.md) - 5-minute setup
- 📖 [**SETUP_GUIDE.md**](docs/SETUP_GUIDE.md) - Detailed setup with Telegram & Calendar
- 📋 [**READINESS_CHECKLIST.md**](docs/READINESS_CHECKLIST.md) - What works and what doesn't

### User Guides
- 🎛️ [**CLI Documentation**](docs/cli.md) - All commands and options
- ⚙️ [**Configuration Guide**](config/README.md) - How to configure Kira
- 🔧 [**Vault API**](docs/vault-api-for-plugins.md) - Working with entities

### Developer Docs
- 🔌 [**Plugin SDK**](docs/sdk.md) - Build your own plugins
- 🏗️ [**Architecture**](docs/architecture.md) - System design
- 📐 [**ADR Index**](docs/adr/) - Architecture Decision Records (16 ADRs)
- 🧪 [**Testing**](tests/) - Unit & integration tests

---

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│                      CLI Interface                       │
│           (inbox, calendar, vault, rollup)              │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼─────┐   ┌────▼─────┐   ┌────▼─────┐
│ Telegram │   │   GCal   │   │   CLI    │
│ Adapter  │   │ Adapter  │   │  Adapter │
└────┬─────┘   └────┬─────┘   └────┬─────┘
     │              │              │
     └──────────────┼──────────────┘
                    │
            ┌───────▼────────┐
            │   Event Bus    │
            │ (pub/sub/retry)│
            └───────┬────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   ┌────▼─────┐ ┌──▼──────┐ ┌──▼─────┐
   │  Inbox   │ │Calendar │ │Rollup  │
   │ Pipeline │ │ Plugin  │ │Pipeline│
   └────┬─────┘ └──┬──────┘ └──┬─────┘
        │          │           │
        └──────────┼───────────┘
                   │
            ┌──────▼──────┐
            │  Host API   │
            │  (Vault)    │
            └──────┬──────┘
                   │
         ┌─────────┼─────────┐
         │         │         │
    ┌────▼────┐ ┌─▼──┐ ┌────▼────┐
    │  Tasks  │ │Notes│ │ Events  │
    │(.md files)│     │(.md files)│
    └─────────┘ └────┘ └─────────┘
```

### Key Concepts

- **Vault**: Markdown-based knowledge base (tasks, notes, events, projects)
- **Adapters**: Connect external systems (Telegram, Google Calendar)
- **Pipelines**: Orchestrate data flow (inbox→normalize→store)
- **Plugins**: Add custom logic (inbox normalizer, calendar sync, deadlines)
- **Event Bus**: Decouple components with pub/sub messaging
- **Host API**: Centralized CRUD operations with validation
- **Sandbox**: Subprocess isolation for plugin security

---

## 🔌 Plugins

### Built-in Plugins

| Plugin | Description | Status |
|--------|-------------|--------|
| **kira-inbox** | Normalize raw items into typed entities | ✅ Ready |
| **kira-calendar** | Google Calendar sync & timeboxing | ✅ Ready |
| **kira-deadlines** | Track deadlines and send reminders | ✅ Ready |
| **kira-code** | Index code repositories | ✅ Ready |
| **kira-mailer** | Email integration (future) | 🚧 Planned |

### Plugin Development

Create your own plugins with the stable SDK:

```python
from kira.plugin_sdk import PluginContext, command, event_handler

@command("hello")
def hello_command(ctx: PluginContext, name: str) -> str:
    return f"Hello, {name}!"

@event_handler("task.created")
def on_task_created(ctx: PluginContext, event: dict) -> None:
    ctx.logger.info(f"New task: {event['entity_id']}")
```

👉 **Learn more:** [Plugin SDK Documentation](docs/sdk.md)

---

## 🎨 Features

### ✅ Core Features (Ready)

- ✅ Markdown-based Vault with YAML frontmatter
- ✅ Stable ID generation (`task-20251007-2330-slug`)
- ✅ Task FSM (todo→doing→review→done|blocked)
- ✅ Bidirectional links and graph validation
- ✅ JSON Schema validation for all entities
- ✅ Event-driven architecture with retry
- ✅ Subprocess sandbox for plugins
- ✅ Structured JSONL logging with traces
- ✅ CLI with all CRUD operations
- ✅ Daily/weekly rollup generation
- ✅ Graph consistency checks

### 🚧 In Progress

- ⚠️ Telegram bot (webhook mode)
- ⚠️ Clarification flow UI
- ⚠️ Daemon mode
- ⚠️ Auto-sync scheduler

### 📅 Planned

- 📋 Web UI (Vault browser)
- 📧 Email adapter
- 🔔 Push notifications
- 📊 Analytics & metrics
- 🤖 AI-powered normalization

---

## 🛠️ Technology Stack

- **Language**: Python 3.11+ (with strict typing)
- **Package Manager**: Poetry
- **CLI Framework**: Click
- **Config**: YAML + environment variables
- **Data Format**: Markdown + YAML frontmatter
- **Validation**: JSON Schema
- **Logging**: Structured JSONL
- **Testing**: pytest
- **Linting**: ruff, black, mypy
- **Adapters**: python-telegram-bot, google-api-client

---

## 📁 Project Structure

```
kira-project/
├── config/                    # Configuration files
│   ├── defaults.yaml          # Default settings
│   ├── kira.yaml.example      # User config template
│   └── env.example            # Environment variables
├── docs/                      # Documentation
│   ├── adr/                   # Architecture Decision Records
│   ├── SETUP_GUIDE.md         # Detailed setup
│   └── cli.md                 # CLI reference
├── src/kira/                  # Main package
│   ├── cli/                   # CLI commands
│   ├── core/                  # Core infrastructure
│   ├── plugin_sdk/            # Plugin SDK
│   ├── plugins/               # Built-in plugins
│   ├── adapters/              # External adapters
│   └── pipelines/             # Data pipelines
├── tests/                     # Tests
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
├── vault/                     # Your Vault (gitignored)
├── kira.yaml                  # Your config (gitignored)
├── pyproject.toml             # Poetry config
└── README.md                  # This file
```

---

## 🧪 Development

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd kira-project

# Install with dev dependencies
poetry install --with dev

# Activate environment
poetry shell

# Run tests
pytest

# Lint
ruff check src/
black --check src/
mypy src/

# Or use Makefile
make test
make lint
```

### Running Tests

```bash
# All tests
pytest

# Unit only
pytest tests/unit/

# Integration only
pytest tests/integration/

# With coverage
pytest --cov=kira --cov-report=html

# Specific test
pytest tests/unit/test_task_fsm.py -v
```

### Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

Please ensure:
- ✅ All tests pass
- ✅ Code is formatted (black, ruff)
- ✅ Type checks pass (mypy)
- ✅ ADRs updated if architecture changes

---

## 📊 Project Status

### Implementation Progress

- **ADR Implementation**: 100% (16/16 completed)
- **Core Infrastructure**: 100%
- **CLI Commands**: 100%
- **Documentation**: 100%
- **Configuration System**: 100%
- **Testing Coverage**: ~90%+ critical paths

### Readiness Level

| Component | Status | Notes |
|-----------|--------|-------|
| Core (Vault, FSM, Events) | ✅ 100% | Production-ready |
| CLI | ✅ 100% | All commands work |
| Configuration | ✅ 100% | Zero hardcode |
| Documentation | ✅ 100% | Comprehensive |
| Inbox Pipeline | ⚠️ 80% | Manual trigger |
| Telegram Adapter | ⚠️ 75% | Needs webhook |
| Calendar Sync | ⚠️ 85% | Manual sync |
| Daemon Mode | ❌ 0% | Planned |

👉 **Detailed status:** [READINESS_CHECKLIST.md](docs/READINESS_CHECKLIST.md)

---

## 🎯 Use Cases

### Personal Task Management
```bash
kira vault new --type task --title "Buy groceries"
kira task add "Write report"
kira task start <task-id>
kira task done <task-id>
kira rollup daily
```

### Note-Taking & Knowledge Base
```bash
kira vault new --type note --title "Meeting Notes"
# Edit vault/notes/note-*.md in your favorite editor
kira validate
```

### Calendar Integration
```bash
kira calendar pull  # Sync from Google Calendar
kira calendar push  # Push back changes
```

### Telegram Quick Capture
```bash
# In Telegram: "TODO: Call John tomorrow"
kira inbox  # Process inbox
```

### Reporting
```bash
kira rollup daily   # Today's summary
kira rollup weekly  # Week's summary
kira diag status    # System health
```

---

## 🔒 Security

- **Sandbox**: Plugins run in subprocess with resource limits
- **Permissions**: Explicit grants required (filesystem, network, etc.)
- **Secrets**: Never committed (`.env`, `.secrets/` gitignored)
- **Validation**: All data validated against JSON schemas
- **Audit**: Permission checks logged

---

## 📜 License

[License TBD]

---

## 🙏 Acknowledgments

Built with:
- [Click](https://click.palletsprojects.com/) - CLI framework
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram API
- [google-api-python-client](https://github.com/googleapis/google-api-python-client) - Google Calendar API
- [PyYAML](https://pyyaml.org/) - YAML parser
- [jsonschema](https://python-jsonschema.readthedocs.io/) - JSON Schema validation

Inspired by:
- [Obsidian](https://obsidian.md/) - Markdown-based knowledge management
- [Org-mode](https://orgmode.org/) - Plain text organization
- [GTD](https://gettingthingsdone.com/) - Task management methodology

---

## 📞 Support & Contact

- **Documentation**: [docs/](docs/)
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

## 🗺️ Roadmap

### v0.2.0 (Next)
- [ ] Daemon mode with systemd service
- [ ] Telegram webhook integration
- [ ] Auto-sync scheduler
- [ ] Clarification UI

### v0.3.0 (Future)
- [ ] Web UI (Vault browser)
- [ ] Email adapter
- [ ] Push notifications
- [ ] Mobile app (optional)

### v1.0.0 (Stable)
- [ ] Full test coverage (95%+)
- [ ] Production deployment guide
- [ ] Multi-user support
- [ ] Plugin marketplace

---

**Made with ❤️ by the Kira team**

⭐ **Star this repo if you find it useful!**

