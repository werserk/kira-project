# Kira

**Your Personal "Jarvis" for Obsidian**

Kira is an AI assistant that makes your Obsidian vault intelligent and self-managing. While Obsidian excels at viewing and editing, **Kira automates the hard parts**: task management, GTD workflows, Zettelkasten linking, and calendar sync.

**Primary Interface:** 📱 Telegram (+ CLI & Web UI)
**Data Storage:** 📝 Standard Markdown (100% Obsidian-compatible)
**Intelligence:** 🤖 Multi-LLM AI (Anthropic, OpenAI, OpenRouter, Ollama)

Think of it as: **Obsidian for viewing, Kira for doing.**

---

## What is Kira?

**Kira = AI Assistant + Obsidian Compatibility**

Managing a personal knowledge system manually is exhausting. Zettelkasten requires discipline. GTD needs constant maintenance. Task management demands structure.

**Kira automates all of this.**

You interact with Kira through **Telegram** (or CLI/Web UI), and it:
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

**Kira solves this.** It's the AI layer that makes your Obsidian vault **intelligent and self-maintaining**, while you interact through simple Telegram messages.

### How It Works

```
┌───────────────────────────────────────────────────────────────┐
│                           YOU                                 │
└──────────────┬─────────────────────────────┬──────────────────┘
               │                             │
               │ Natural Language            │ Visual Interface
               │ (Telegram/CLI/Web)          │ (Manual Editing)
               ↓                             ↓
    ┌──────────────────────┐      ┌──────────────────────┐
    │   KIRA (AI Layer)    │      │   OBSIDIAN (UI)      │
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
1. **Via Kira (Telegram)**: You send *"Create task: Review Q4 report by Friday"*
   - Kira processes with AI, validates, applies FSM rules
   - Writes `tasks/task-20251011-1420.md` to vault

2. **Via Obsidian**: You manually create a note or edit existing task
   - Obsidian writes directly to vault as markdown
   - Kira sees the change and validates on next sync

3. **Result**: Both tools work with the same files
   - Kira ensures structure, validation, automation
   - Obsidian provides beautiful UI and manual control
   - Your vault stays consistent and never corrupts

---

## Two Modes of Operation

Kira operates in two complementary modes:

### 🤖 Mode 1: AI Assistant (Primary)

**Interact naturally, Kira handles the complexity.**

Your primary interface is **Telegram** (with CLI and Web UI as alternatives). You send messages like:

```
You: "Create a task to review the Q4 report by Friday"
Kira: ✓ Created task-20251015-1420
      ✓ Due: 2025-10-11T17:00:00Z
      ✓ Added to calendar
      ✓ Linked to project Q4-planning
```

**Kira handles:**
- Task creation with proper FSM state management
- Bidirectional link updates in your graph
- Calendar synchronization
- Data validation and integrity checks
- Daily summaries and reminders

**You get:**
- Hands-free knowledge management
- GTD/Zettelkasten automation
- Natural language interface
- Real-time updates via Telegram

### 📝 Mode 2: Obsidian Compatibility (Viewing & Editing)

**Your vault is 100% Obsidian-compatible.**

All data is stored as **standard markdown + YAML frontmatter**:

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

**Open your vault in Obsidian to:**
- 👁️ View your entire knowledge graph
- ✏️ Manually edit notes and tasks
- 🔍 Use Obsidian's powerful search
- 📊 Leverage Obsidian plugins (Graph View, Dataview, etc.)
- 🎨 Customize with themes and CSS

**Why Both Modes?**

| Use Case | Tool | Why |
|----------|------|-----|
| Quick task creation | Telegram → Kira | Fastest, hands-free |
| Review knowledge graph | Obsidian | Best visualization |
| Daily planning | Telegram → Kira | Conversational interface |
| Deep work on notes | Obsidian | Focused editing environment |
| Automation & workflows | Kira | Intelligence layer |
| Manual refinement | Obsidian | Full control |

**The synergy:** Kira maintains structure and automation. Obsidian provides the perfect viewing and editing experience.

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
         └─────────────┴────┬────────┴──────────────┘
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
         │  ┌─────────┐  ┌──────────┐  ┌─────────┐  │
         │  │   FSM   │  │ Validator│  │ Plugins │  │
         │  └─────────┘  └──────────┘  └─────────┘  │
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
         │  ┌─────┐  ┌─────┐  ┌──────┐  ┌────────┐  │
         │  │Tasks│  │Notes│  │Events│  │Projects│  │
         │  └─────┘  └─────┘  └──────┘  └────────┘  │
         └─────────────────┬────────────────────────┘
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

### For Teams

Kira's architecture is designed for team collaboration from the ground up:
- **Audit Trail**: Every change logged with user/trace ID for accountability
- **Permissions**: Plugin sandboxing enforces access control and security boundaries
- **API-First**: HTTP API enables integration with team workflows
- **Collaborative Workflows**: Shared vault with conflict resolution (in development)

---

## Kira + Obsidian: Better Together

**Think of Kira and Obsidian as partners, not competitors:**

| Capability | Kira | Obsidian | Together |
|------------|------|----------|----------|
| **AI Assistant** | ✅ Native (Telegram/CLI) | ❌ Limited | 🚀 Chat-based automation |
| **Visual Graph** | ⚠️ Basic | ✅ Excellent | 🚀 Kira maintains, Obsidian displays |
| **Data Validation** | ✅ Schema + FSM | ❌ None | 🚀 Integrity guaranteed |
| **Manual Editing** | ⚠️ CLI/API | ✅ Best-in-class | 🚀 Edit freely, Kira validates |
| **Task FSM** | ✅ Automated | ❌ Manual | 🚀 State machine enforced |
| **Calendar Sync** | ✅ Two-way | 🔌 Via plugins | 🚀 Seamless integration |
| **Mobile Access** | ✅ Telegram | ✅ Mobile app | 🚀 Full mobility |
| **Automation** | ✅ Event-driven | ❌ Manual | 🚀 Set-and-forget workflows |
| **Plugin System** | ✅ Sandboxed | ✅ Rich ecosystem | 🚀 Best of both worlds |

### Comparison with Other Tools

| Feature | Kira + Obsidian | Notion | Roam Research | Org-mode |
|---------|-----------------|--------|---------------|----------|
| **Data Ownership** | ✅ Local files | ❌ Cloud only | ❌ Cloud only | ✅ Local |
| **AI Automation** | ✅ Native | ⚠️ Limited | ❌ None | ❌ None |
| **Validation** | ✅ Enforced | ⚠️ Soft | ❌ None | ❌ None |
| **Telegram Bot** | ✅ Built-in | ❌ None | ❌ None | ❌ None |
| **Visual Editor** | ✅ Obsidian | ✅ Native | ✅ Native | ⚠️ Emacs |
| **Offline-First** | ✅ Always | ❌ No | ❌ No | ✅ Yes |

---

## Real-World Use Cases

### 1. **Morning Routine via Telegram**
```
[Telegram - 7:30 AM]
You: "Good morning, what's on my plate?"

Kira: Good morning! Here's your day:

      📋 Tasks (3):
      • Review PR #45 (due 2pm) - HIGH
      • Team standup (10am, blocked 30min)
      • Draft Q4 goals

      📅 Events (2):
      • 10:00 Team Standup (Zoom)
      • 14:00 Client call (45min)

      📊 Yesterday: 4 tasks completed, 2h focused work

You: "Create a task to prepare slides for the client call"

Kira: ✓ Created task-20251008-0732
      ✓ Due: Today 13:30 (30min before call)
      ✓ Linked to event "Client call"
      ✓ Calendar timebox created

[You open Obsidian]
→ See all tasks in your vault with proper links
→ Edit notes manually if needed
→ View your knowledge graph
→ Kira keeps everything validated and synced
```

**Workflow:**
- **Telegram**: Quick task creation and status updates
- **Obsidian**: Review context, edit notes, visualize connections
- **Kira**: Maintains integrity, enforces FSM, syncs calendar

### 2. **Zettelkasten Automation**
```
[Telegram - During research]
You: "Create note: Key insight from 'Atomic Habits' -
     small changes compound. 1% better daily = 37x improvement yearly"

Kira: ✓ Created note-20251008-1125
      ✓ Tagged: #books, #productivity, #habits
      ✓ Auto-linked to: [[note-habit-formation]]
      ✓ Added to reading project

You: "What have I learned about productivity this week?"

Kira: Found 7 notes on productivity:
      • note-atomic-habits (Oct 8)
      • note-deep-work (Oct 6)
      • note-pomodoro-technique (Oct 5)

      Common themes: Focus, habit stacking, timeboxing

      Would you like a weekly rollup?

[Open in Obsidian]
→ Beautiful graph view of all connected notes
→ Dataview queries for book notes
→ Manual refinement of connections
→ Kira maintains bidirectional links automatically
```

**Value:**
- **Create**: Via Telegram, hands-free
- **Maintain**: Kira auto-links and validates
- **Explore**: Obsidian's graph view
- **Query**: RAG-powered semantic search

### 3. **GTD Workflow Automation**
```
[Telegram - Inbox Processing]
You: "I need to organize next week's team workshop"

Kira: 📥 Added to inbox for clarification.

      This seems like a project. Would you like me to:
      1. Create project "Team Workshop"
      2. Break into tasks (venue, agenda, invites)
      3. Set deadline for next week

      Confirm?

You: "Yes, deadline Friday 5pm"

Kira: ✓ Created proj-team-workshop
      ✓ Created 5 subtasks (todo state)
      ✓ Deadline: 2025-10-11 17:00
      ✓ Calendar blocks created

      First task: "Book venue" - want to start now?

[Later in Obsidian]
→ Open project note
→ See all linked tasks in clean format
→ Add meeting notes and context
→ Kira ensures tasks follow FSM rules
```

**GTD Made Easy:**
- **Capture**: Telegram inbox (no thinking)
- **Clarify**: Kira asks smart questions
- **Organize**: Automatic project/task creation
- **Review**: Obsidian for big picture
- **Execute**: State machine enforces flow

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

### 1. **Obsidian-First Compatibility**
100% standard markdown. Use Obsidian for viewing/editing. Kira for intelligence.

### 2. **Data Sovereignty**
Your data is yours. Always in readable format. No cloud required. Obsidian-compatible always.

### 3. **Telegram-First Interaction**
Primary interface is conversational. CLI and Web UI for power users.

### 4. **Correctness Over Speed**
Every write is validated. Crashes can't corrupt state. Your Obsidian vault stays clean.

### 5. **Automation Over Manual Work**
Let Kira handle structure, linking, validation. You focus on thinking.

### 6. **Explicit State Management**
Task FSM enforces rules. No tasks stuck in limbo. Clear transitions.

### 7. **Fail Loud**
Validation errors surface immediately. Malformed data quarantined, never corrupts your vault.

---

## Who Is Kira For?

**Ideal Users:**
- 📝 **Obsidian users** who want automation (primary target!)
- 🧑‍💻 **Developers** who want hackable PKM with API access
- 🎯 **GTD practitioners** tired of manual maintenance
- 🔬 **Researchers** managing complex Zettelkasten
- 👨‍💼 **Solopreneurs** needing task + knowledge management
- 📱 **Mobile users** who want Telegram-based interaction

**Not Ideal For:**
- Users happy with manual Obsidian workflows
- Teams needing real-time collaborative editing
- Users who don't want AI automation
- People who prefer GUI-only interaction

---

## Development Team

Kira is developed by a dedicated team focused on delivering enterprise-grade personal knowledge management.

**Architecture Decision Records (ADRs):**
Kira documents every major design decision. Read `/docs/adr/` to understand the technical rationale behind architectural choices.

**Team Onboarding:**
New team members should review:
- Architecture documentation in `/docs`
- Test suite for understanding system behavior
- ADRs for context on design decisions
- Plugin SDK for extensibility patterns

---

## Contact & Support

For questions, issues, or feature requests, contact the development team through internal channels.

---

## Technical Foundations

Kira's design is informed by proven methodologies:
- **GTD (Getting Things Done)** - David Allen's workflow methodology
- **Zettelkasten** - Niklas Luhmann's note-taking system
- **Local-first software principles** - Data ownership and offline-first architecture
- **Production engineering patterns** - From distributed systems and database design

Built with modern Python stack: FastAPI, Pydantic, Anthropic SDK, and battle-tested libraries.

---

**Enterprise-grade personal knowledge management for demanding professionals.**

*Version 0.1.0-alpha | Last Updated: 2025-10-08*

---

© 2025 Kira Development Team. All rights reserved.
