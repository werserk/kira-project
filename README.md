# Kira

**Your AI-powered Personal Knowledge Management System**

Kira is a production-ready Personal Knowledge Management (PKM) system that combines the flexibility of local markdown files with the power of enterprise-grade data management. Think of it as your personal operating system for thoughts, tasks, and knowledge—backed by battle-tested engineering principles.

---

## What is Kira?

Kira transforms how you manage personal knowledge by treating your notes, tasks, and events as **first-class data entities** with:

- **Integrity**: Every change is validated, logged, and atomic
- **Intelligence**: Natural language interface powered by LLMs (Anthropic, OpenAI, OpenRouter, Ollama)
- **Flexibility**: Your data lives in plain markdown files you own forever
- **Extensibility**: Rich plugin system for custom workflows
- **Reliability**: Built on principles from distributed systems and production engineering

### The Problem Kira Solves

Modern knowledge workers face a dilemma:
- 📝 **Note-taking apps** are simple but lack structure and automation
- 🗄️ **Database tools** are powerful but complex and lock your data
- 🤖 **AI assistants** are smart but don't maintain state or validate actions
- 🔗 **Sync services** connect tools but lose data integrity guarantees

**Kira bridges all four.** It's a local-first system with database reliability, AI intelligence, and an open plugin ecosystem—all while your data stays in readable markdown files.

---

## Core Capabilities

### 🧠 AI Agent with Memory

Kira includes a conversational AI agent that understands your context and executes tasks:

```
You: "Schedule a review of project Alpha next Tuesday"
Kira: ✓ Created task "Review project Alpha"
      ✓ Set due date: 2025-10-15
      ✓ Added calendar timebox
      ✓ Linked to project Alpha
```

**Key Features:**
- **Multi-Provider Support**: Use Anthropic Claude, OpenAI GPT, OpenRouter, or local Ollama
- **Plan → Execute → Verify**: Review actions before they happen (dry-run mode)
- **Conversation Memory**: Maintains context across interactions
- **RAG (Retrieval-Augmented Generation)**: Queries your vault for relevant context
- **Structured Execution**: All actions logged with audit trail

### 📦 Vault: Your Knowledge Base

The Vault is where your data lives—organized, validated, and always accessible:

```
vault/
├── tasks/          # Todo items with FSM state management
├── notes/          # Free-form notes with bidirectional links
├── events/         # Calendar events with sync capabilities
├── projects/       # Project tracking with tasks hierarchy
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

### 🔄 Task State Machine

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

### 🔌 Plugin System

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

**Plugin Features:**
- **Sandboxed Execution**: Memory limits, timeouts, permission controls
- **Host API Access**: Read/write vault through validated interface
- **Event Bus Integration**: React to entity changes
- **Configuration**: Plugin-specific settings via YAML

**Built-in Plugins:**
- `kira-inbox`: Handles ambiguous inputs with clarification workflows
- `kira-calendar`: Syncs with Google Calendar (two-way)
- `kira-deadlines`: Proactive reminders for due dates
- `kira-rollup`: Generates daily/weekly summaries

### 🔗 External Integrations

Kira connects with your existing tools:

**Telegram Bot/Userbot**
```
Send message: "Create task: Review PRs"
Kira replies: ✓ Task task-20251008-1342 created
```

**Google Calendar Sync**
- Import events as vault entities
- Two-way sync with echo-break for conflict resolution
- Automatic timebox creation for tasks

**File System Adapter**
- Watch directories for new markdown files
- Auto-import with schema normalization

### ⚙️ Production-Grade Architecture

Kira is built with principles from distributed systems:

#### 1. **Single Writer Pattern (ADR-001)**
All writes go through `HostAPI`—one source of truth, no race conditions.

#### 2. **Atomic Operations**
```
write_temp → fsync(temp) → rename → fsync(dir)
```
Crash-safe writes guaranteed by OS atomicity.

#### 3. **Idempotent Event Processing (ADR-003)**
```
event_id = sha256(source, external_id, payload)
```
Deduplicated in SQLite—events processed exactly once.

#### 4. **Schema Validation**
Every entity validated against JSON schemas before write:
- Required fields: `id`, `title`, `created`, `updated`, `status`
- Type checking, enum constraints, regex patterns
- Custom business rules via FSM guards

#### 5. **UTC Time Discipline (ADR-005)**
All timestamps stored in UTC, DST-aware operations ensure correctness.

#### 6. **Structured Logging**
Every operation correlated by `trace_id`, `entity_id`, or `event_id`:
```json
{
  "event": "entity.created",
  "entity_id": "task-20251008-1342",
  "trace_id": "a1b2c3d4-...",
  "timestamp": "2025-10-08T13:42:17Z"
}
```

#### 7. **Link Graph Maintenance**
Bidirectional links automatically updated:
- `[[note-123]]` in content → forward link
- `backlinks` query → automatic inverse
- Orphan detection and graph queries

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Ingress Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ Telegram │  │   CLI    │  │  GCal    │  │  HTTP API  │ │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └──────┬─────┘ │
└────────┼─────────────┼─────────────┼──────────────┼────────┘
         │             │             │              │
         └─────────────┴─────────────┴──────────────┘
                            ↓
         ┌──────────────────────────────────────────┐
         │         Event Bus (At-Least-Once)        │
         │   ┌────────────────────────────────┐     │
         │   │  Idempotency Layer (SQLite)    │     │
         │   └────────────────────────────────┘     │
         └─────────────────┬────────────────────────┘
                           ↓
         ┌──────────────────────────────────────────┐
         │        Business Logic Layer              │
         │  ┌─────────┐  ┌──────────┐  ┌─────────┐ │
         │  │   FSM   │  │ Validator│  │ Plugins │ │
         │  └─────────┘  └──────────┘  └─────────┘ │
         └─────────────────┬────────────────────────┘
                           ↓
         ┌──────────────────────────────────────────┐
         │    Host API (Single Writer Pattern)      │
         │  ┌──────────────────────────────────┐    │
         │  │  Atomic Writes + File Locks      │    │
         │  └──────────────────────────────────┘    │
         └─────────────────┬────────────────────────┘
                           ↓
         ┌──────────────────────────────────────────┐
         │              Vault Storage               │
         │     (Plain Markdown + Frontmatter)       │
         │  ┌─────┐  ┌─────┐  ┌──────┐  ┌───────┐  │
         │  │Tasks│  │Notes│  │Events│  │Projects│ │
         │  └─────┘  └─────┘  └──────┘  └───────┘  │
         └──────────────────┬───────────────────────┘
                           ↓
         ┌──────────────────────────────────────────┐
         │          External Systems                │
         │  ┌──────────┐  ┌──────────────────────┐  │
         │  │  GCal    │  │  Future: JIRA, etc   │  │
         │  │  Sync    │  │                      │  │
         │  └──────────┘  └──────────────────────┘  │
         └──────────────────────────────────────────┘
```

### Data Flow Example: "Create Task via Telegram"

1. **Ingress**: User sends message `"Buy milk tomorrow 5pm"`
2. **Event Bus**: Publishes `telegram.message` event with deduplication
3. **Plugin**: Inbox plugin parses with LLM, creates structured data
4. **Validation**: Schema validator checks required fields
5. **FSM**: Task FSM validates initial state is `todo`
6. **Host API**: Generates ID `task-20251008-1342`, writes atomically
7. **Vault**: File `tasks/task-20251008-1342.md` created with frontmatter
8. **Link Graph**: Updates graph with any `[[links]]` from content
9. **Event Emission**: Publishes `entity.created` event
10. **External Sync**: GCal adapter creates calendar event
11. **Response**: Telegram bot confirms: `✓ Task created with ID task-20251008-1342`

---

## Why Kira?

### For Personal Use

**You want:**
- ✅ Complete control over your data (plain markdown files)
- ✅ AI assistant that learns from your vault
- ✅ Automatic task management without manual overhead
- ✅ Integration with calendar, Telegram, and more
- ✅ Confidence that your data won't corrupt or lose integrity

**Traditional tools fall short:**
- ❌ Notion/Roam: Proprietary formats, vendor lock-in
- ❌ Obsidian: No validation, manual linking, limited automation
- ❌ Todoist: Tasks only, no notes or knowledge management
- ❌ ChatGPT: Stateless, can't manage persistent data

### For Developers

**You want:**
- ✅ Hackable system with clean architecture
- ✅ Plugin system for custom workflows
- ✅ Production patterns (atomic writes, validation, logging)
- ✅ Test coverage (744+ tests, 91% pass rate)
- ✅ Clear ADRs explaining design decisions

**Kira provides:**
- 📖 Well-documented SDK (`kira.plugin_sdk`)
- 🧪 Extensive test suite you can learn from
- 🏗️ Architecture Decision Records (ADRs) for every major choice
- 🔧 CLI for automation and scripting
- 🐳 Docker support for deployment

### For Teams (Future)

While Kira is currently personal-focused, the architecture supports multi-user:
- **Conflict Resolution**: CRDTs/OT for collaborative editing (planned)
- **Permissions**: Plugin sandboxing already enforces access control
- **Audit Trail**: Every change logged with user/trace ID
- **API-First**: HTTP API ready for client apps

---

## Key Differentiators

| Feature | Kira | Obsidian | Notion | Org-mode |
|---------|------|----------|--------|----------|
| **Data Format** | Markdown + YAML | Markdown | Proprietary | Org format |
| **Validation** | ✅ Schema + FSM | ❌ None | ⚠️ Soft | ❌ None |
| **AI Integration** | ✅ Native LLM | 🔌 Plugins | ✅ Native | ❌ Manual |
| **Atomic Writes** | ✅ OS-level | ❌ No | ☁️ Cloud | ⚠️ Manual |
| **Plugin Sandbox** | ✅ Enforced | ⚠️ Trusted | 🚫 N/A | ⚠️ Trusted |
| **Event Bus** | ✅ Built-in | ❌ No | 🚫 N/A | ❌ No |
| **External Sync** | ✅ GCal, Telegram | 🔌 Plugins | ✅ Many | 🔌 Elisp |
| **Audit Logging** | ✅ JSONL | ❌ No | ⚠️ Limited | ❌ No |
| **Open Source** | ✅ MIT | 💰 Freemium | ❌ Closed | ✅ GPL |

---

## Real-World Use Cases

### 1. **Project Management**
```yaml
# vault/projects/proj-website-redesign.md
---
id: proj-website-redesign
title: Website Redesign Q4
status: active
start_date: 2025-10-01
target_date: 2025-12-31
owner: [[contact-john]]
tags: [web, design, q4]
---

## Overview
Complete redesign of company website with modern framework.

## Tasks
- [[task-20251008-001]] Research design systems
- [[task-20251008-002]] Create wireframes
- [[task-20251008-003]] Implement prototype
```

**Kira automatically:**
- Tracks task completion percentage
- Sends reminders 1 week before deadline
- Creates weekly rollup of progress
- Syncs milestones to Google Calendar

### 2. **Research & Learning**
```markdown
# vault/notes/note-atomic-habits.md
---
id: note-atomic-habits
title: Atomic Habits - Key Takeaways
tags: [books, productivity, habits]
source: "Atomic Habits by James Clear"
created: 2025-10-08T10:30:00Z
---

## Core Concept
Small changes compound over time. 1% better each day.

Related: [[note-habit-formation]], [[proj-morning-routine]]
```

**Kira enables:**
- Find all notes related to "productivity"
- Generate weekly summary of learnings
- Link concepts across notes automatically
- RAG queries: "What did I learn about habits?"

### 3. **Daily Operations**
```
Morning:
  You: "What's on my plate today?"
  Kira: You have 3 tasks:
        • Review PR #45 (due 2pm)
        • Team standup (10am, timeboxed)
        • Draft Q4 goals (high priority)

Afternoon:
  You: "Done with PR review, notes in the task"
  Kira: ✓ Updated task-20251008-045 to 'done'
        ✓ Logged completion time: 1.5h
        ✓ Notified team via Telegram

Evening:
  You: "Show me today's rollup"
  Kira: Daily Rollup - 2025-10-08
        ✓ 5 tasks completed
        ✓ 2 notes created
        ✓ 3h focused work
        → Tomorrow: Start Q4 planning
```

---

## Technology Stack

**Core:**
- Python 3.12+ (Modern async/await patterns)
- Poetry (Dependency management)
- YAML + Markdown (Human-readable data format)

**Data Layer:**
- Local file system (Atomic operations via `fcntl`)
- SQLite (Idempotency tracking)
- JSON Schema (Validation)

**AI & LLM:**
- Anthropic Claude (Planning & reasoning)
- OpenAI GPT (Fallback)
- OpenRouter (Multi-model access)
- Ollama (Local/offline models)

**Integrations:**
- `python-telegram-bot` (Telegram bot/userbot)
- `google-api-python-client` (Google Calendar sync)
- FastAPI (HTTP API for agent)
- Uvicorn (ASGI server)

**Development:**
- Pytest (744+ tests, 91% coverage)
- Black + Ruff (Formatting & linting)
- Mypy (Type checking)
- Pre-commit hooks (Quality gates)

---

## Project Status

**Current Version:** `0.1.0-alpha` (Released 2025-10-08)

**Maturity:**
- ✅ Core features stable (Vault, FSM, validation)
- ✅ CLI ready for daily use
- ✅ AI agent functional (multi-provider support)
- ⚠️ Integrations in alpha (Telegram, GCal behind flags)
- ⚠️ Plugin system under active development

**Test Coverage:**
- 744/821 tests passing (91%)
- 700+ unit tests
- 24 integration tests
- CI/CD green status

**Known Limitations:**
- Google Calendar sync is import-only (two-way sync planned)
- Telegram adapter requires manual setup
- Performance optimization pending for large vaults (>10k entities)
- Some DST edge cases under investigation

---

## Roadmap

### Phase 7 (Next Release)
- 🔄 Full two-way GCal sync with conflict resolution
- 📱 Mobile companion app (read-only)
- 🎨 Web UI for vault browsing
- ⚡ Performance optimization (indexing, caching)

### Phase 8 (Future)
- 🤝 Multi-user collaboration (operational transforms)
- 🔐 End-to-end encryption for sensitive notes
- 📊 Analytics dashboard (productivity metrics)
- 🌐 WebDAV/S3 sync for vault backup

### Long-Term Vision
- 🧠 Semantic search with vector embeddings
- 🔗 Integration marketplace (JIRA, GitHub, Slack)
- 🎯 Goal tracking with OKRs
- 📈 Predictive insights (time estimates, completion probability)

---

## Philosophy & Design Principles

### 1. **Data Sovereignty**
Your data is yours. Always in readable format. No cloud required.

### 2. **Local-First**
Works offline. Sync is optional. Data never leaves your machine unless you decide.

### 3. **Correctness Over Speed**
Every write is validated. Crashes can't corrupt state. Data integrity is non-negotiable.

### 4. **Progressive Disclosure**
Start simple (CLI for tasks), grow complex (plugins, integrations, AI).

### 5. **Composable Tools**
Each component usable independently. CLI, Agent, Vault—mix and match.

### 6. **Explicit Over Implicit**
State transitions require clear triggers. No hidden magic.

### 7. **Fail Loud**
Validation errors surface immediately. Malformed data quarantined, not silently ignored.

---

## Who Is Kira For?

**Ideal Users:**
- 🧑‍💻 Developers who want hackable PKM
- 📝 Knowledge workers drowning in scattered notes
- 🎯 Productivity enthusiasts seeking automation
- 🔬 Researchers managing complex information
- 👨‍💼 Solopreneurs tracking projects and clients

**Not Ideal For:**
- Users wanting zero-config, plug-and-play solution
- Teams needing real-time collaboration (not yet supported)
- Non-technical users uncomfortable with CLI/YAML

---

## Contributing

Kira is open source (MIT License) and welcomes contributions!

**Areas Where Help Is Needed:**
- 🐛 Bug reports and edge case testing
- 📖 Documentation improvements
- 🔌 Plugin development
- 🌍 Internationalization (i18n)
- 🎨 UI/UX design for web interface

**Architecture Decision Records (ADRs):**
Kira documents every major design decision. Read `/docs/adr/` to understand why things are the way they are.

---

## License

MIT License - See [LICENSE](LICENSE) file.

**In short:** Use Kira however you want—personal, commercial, modified. Attribution appreciated but not required.

---

## Support & Community

- 📧 Issues: [GitHub Issues](https://github.com/werserk/kira-project/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/werserk/kira-project/discussions)
- 📖 Documentation: `/docs` directory (coming soon)
- 🐦 Updates: Follow development on GitHub

---

## Acknowledgments

Kira builds on ideas from:
- **GTD (Getting Things Done)** - David Allen's workflow methodology
- **Zettelkasten** - Niklas Luhmann's note-taking system
- **Obsidian** - Inspiration for local-first markdown
- **Org-mode** - Plain-text task management done right

Special thanks to the open-source community for tools like FastAPI, Pydantic, Anthropic SDK, and countless others.

---

**Built with ❤️ for knowledge workers who demand more from their tools.**

*Version 0.1.0-alpha | Last Updated: 2025-10-08*
