# Kira Demo Commands & Usage Examples

This file contains practical examples of using Kira across different interfaces and workflows.

---

## Table of Contents

1. [CLI Basics](#cli-basics)
2. [Task Management](#task-management)
3. [AI Agent Usage](#ai-agent-usage)
4. [Telegram Bot Examples](#telegram-bot-examples)
5. [Calendar Integration](#calendar-integration)
6. [Note & Knowledge Management](#note--knowledge-management)
7. [Advanced Workflows](#advanced-workflows)

---

## CLI Basics

### Getting Started

```bash
# Check Kira version and configuration
kira --help

# System health check
kira doctor

# Validate vault integrity
kira validate

# View today's agenda
kira today

# Personal statistics
kira stats
```

### Vault Operations

```bash
# Initialize a new vault
kira vault init

# Create a new entity
kira vault new --type task --title "My Task"
kira vault new --type note --title "Meeting Notes"
kira vault new --type event --title "Team Standup"

# List all entities
kira vault list --type task
kira vault list --type note

# Read entity details
kira vault get task-20251008-1234

# Validate specific entity
kira vault validate task-20251008-1234
```

---

## Task Management

### Creating Tasks

```bash
# Simple task
kira task add "Buy groceries"

# Task with due date
kira task add "Submit report" --due 2025-10-15

# Task with tags
kira task add "Review PRs" --tags work,code

# Task with priority
kira task add "Fix critical bug" --priority high

# Task with assignee
kira task add "Team meeting prep" --assignee john@example.com
```

### Listing Tasks

```bash
# All tasks
kira task list

# Filter by status
kira task list --status todo
kira task list --status doing
kira task list --status done

# Filter by tags
kira task list --tags work
kira task list --tags urgent,high-priority

# Filter by date range
kira task list --due-before 2025-10-20
kira task list --created-after 2025-10-01

# Combine filters
kira task list --status todo --tags work --due-before 2025-10-20
```

### Task Lifecycle

```bash
# Start working on a task
kira task start task-20251008-1234

# Update task details
kira task update task-20251008-1234 --title "New Title"
kira task update task-20251008-1234 --due 2025-10-20
kira task update task-20251008-1234 --tags urgent,reviewed

# Complete a task
kira task done task-20251008-1234

# Reopen a completed task (requires reason)
kira task reopen task-20251008-1234 --reason "Found new requirements"

# Block a task
kira task block task-20251008-1234 --reason "Waiting for API access"

# Delete a task (with confirmation)
kira task delete task-20251008-1234
```

### Task Transitions (FSM)

```bash
# Valid transitions:
# todo → doing (requires assignee or start time)
kira task start task-20251008-1234

# doing → done (sets completion timestamp)
kira task done task-20251008-1234

# done → doing (requires reopen reason)
kira task reopen task-20251008-1234 --reason "Need to revise"

# any → blocked (requires block reason)
kira task block task-20251008-1234 --reason "Dependency missing"

# blocked → todo (unblock)
kira task unblock task-20251008-1234
```

---

## AI Agent Usage

### Starting the Agent

```bash
# Start HTTP service (default port 8000)
kira agent start

# Custom port
kira agent start --port 8080

# With debug logging
kira agent start --verbose
```

### Using the Agent API

#### 1. Plan Only (Dry-run)

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create three tasks for project setup",
    "execute": false
  }'
```

**Response:**
```json
{
  "status": "ok",
  "results": [{
    "plan": "I will create three tasks",
    "reasoning": "Breaking project setup into manageable steps",
    "steps": [
      {"tool": "task_create", "args": {"title": "Initialize repository"}, "dry_run": true},
      {"tool": "task_create", "args": {"title": "Setup CI/CD"}, "dry_run": true},
      {"tool": "task_create", "args": {"title": "Configure environment"}, "dry_run": true}
    ]
  }],
  "trace_id": "plan-only"
}
```

#### 2. Execute (Real Actions)

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a task to review quarterly goals by Friday",
    "execute": true
  }'
```

**Response:**
```json
{
  "status": "success",
  "results": [
    {
      "tool": "task_create",
      "result": {
        "id": "task-20251008-1534",
        "title": "Review quarterly goals",
        "status": "todo",
        "due": "2025-10-11T17:00:00Z"
      }
    }
  ],
  "trace_id": "abc123..."
}
```

#### 3. Complex Queries

```bash
# Multi-step workflow
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a project for Q4 planning with 5 tasks",
    "execute": true
  }'

# Information retrieval
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What tasks are due this week?",
    "execute": false
  }'

# Daily summary
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Generate a daily rollup for today",
    "execute": true
  }'
```

#### 4. Health Check

```bash
# Check service health
curl http://localhost:8000/health

# Get version info
curl http://localhost:8000/agent/version

# Prometheus metrics
curl http://localhost:8000/metrics
```

---

## Telegram Bot Examples

### Starting the Bot

```bash
# Start with polling (for development/no public IP)
kira telegram start --token YOUR_BOT_TOKEN --verbose

# With whitelist (security)
export TELEGRAM_ALLOWED_CHAT_IDS="123456789,987654321"
kira telegram start --token YOUR_BOT_TOKEN
```

### Telegram Conversations

#### Basic Task Creation

```
You: Create a task: Buy milk

Bot: ✅ Step 1: task_create
     ID: task-20251008-1620
     Title: Buy milk
     Status: todo
```

#### Complex Request

```
You: I need to prepare for next week's client presentation.
     Create tasks for slide deck, rehearsal, and feedback review.

Bot: ✅ Step 1: task_create
     ID: task-20251008-1621, Title: Create slide deck

     ✅ Step 2: task_create
     ID: task-20251008-1622, Title: Rehearse presentation

     ✅ Step 3: task_create
     ID: task-20251008-1623, Title: Review client feedback
```

#### Task Queries

```
You: What tasks do I have today?

Bot: 📋 Tasks for today (3):

     1. Review Q4 goals (due 5:00 PM)
     2. Team standup (10:00 AM - 10:30 AM)
     3. Update documentation (no due date)
```

#### Task Updates

```
You: Mark task-20251008-1620 as done

Bot: ✅ Step 1: task_update
     Task task-20251008-1620 marked as done
     Completion time: 2025-10-08T16:45:00Z
```

#### Daily Summaries

```
You: Generate my daily summary

Bot: 📊 Daily Rollup (2025-10-08)

     ✅ Completed (4 tasks):
     - Review PRs
     - Team meeting
     - Update wiki
     - Code review

     📋 In Progress (2 tasks):
     - Feature implementation
     - Bug fixes

     ⏰ Upcoming:
     - Client call tomorrow 2:00 PM
```

### Telegram Commands

```
/start - Initialize bot
/help - Show available commands
/today - Today's agenda
/tasks - List all tasks
/stats - Personal statistics
/rollup - Generate daily summary
```

---

## Calendar Integration

### Google Calendar Sync

```bash
# Pull events from Google Calendar
kira calendar pull

# Pull from specific calendar
kira calendar pull --calendar-id primary

# Pull with date range
kira calendar pull --days 30

# Push tasks to calendar
kira calendar push

# Push specific entities
kira calendar push --entity-ids task-20251008-1234,task-20251008-1235

# Dry-run (preview without changes)
kira calendar push --dry-run

# Reconcile conflicts
kira calendar reconcile
```

### Schedule Management

```bash
# View today's schedule
kira schedule view --today

# View specific date
kira schedule view --date 2025-10-15

# View week
kira schedule view --week

# Find scheduling conflicts
kira schedule conflicts

# Create timebox for task
kira calendar timebox task-20251008-1234 --duration 60
```

### Event Operations

```bash
# Create event
kira vault new --type event \
  --title "Team Standup" \
  --start "2025-10-09T10:00:00Z" \
  --end "2025-10-09T10:30:00Z"

# List events
kira vault list --type event

# Sync specific event to GCal
kira calendar push --entity-ids event-20251008-1100
```

---

## Note & Knowledge Management

### Creating Notes

```bash
# Simple note
kira note add "Key insight from book"

# Note with tags
kira note add "Sprint retrospective notes" --tags retrospective,team

# Note with links
kira note add "Project Alpha planning" --links proj-alpha,task-20251008-1234

# Note from file
kira note import ./meeting-notes.md
```

### Searching

```bash
# Full-text search
kira search "quarterly goals"

# Search in specific entity types
kira search "API" --type note
kira search "urgent" --type task

# Search with date filter
kira search "meeting" --after 2025-10-01

# Search with tags
kira search "planning" --tags team
```

### Link Management

```bash
# Show entity links
kira links show task-20251008-1234

# Show backlinks
kira links backlinks note-20251008-1500

# Show graph around entity
kira links graph task-20251008-1234 --depth 2

# Find orphaned entities
kira links orphans

# Validate link integrity
kira links validate
```

### Projects

```bash
# Create project
kira project add "Q4 Initiative"

# List projects
kira project list

# Add task to project
kira project add-task proj-q4-initiative task-20251008-1234

# Project status
kira project status proj-q4-initiative

# Project timeline
kira project timeline proj-q4-initiative
```

---

## Advanced Workflows

### Daily Routine

```bash
#!/bin/bash
# morning_routine.sh

echo "🌅 Good morning! Here's your day:"
echo ""

# Today's agenda
kira today

# Check for conflicts
kira schedule conflicts

# Pull calendar events
kira calendar pull --days 1

echo ""
echo "Ready to start the day! 🚀"
```

### Evening Review

```bash
#!/bin/bash
# evening_review.sh

echo "🌙 End of day review:"
echo ""

# Generate daily rollup
kira rollup daily

# Statistics
kira stats --today

# Backup vault
make backup

echo ""
echo "Great work today! 💪"
```

### Weekly Planning

```bash
#!/bin/bash
# weekly_planning.sh

echo "📅 Weekly Planning:"
echo ""

# Generate weekly rollup
kira rollup weekly

# Review next week's schedule
kira schedule view --week --offset 1

# List incomplete tasks
kira task list --status todo,doing

# Pull calendar for next week
kira calendar pull --days 7

echo ""
echo "Week planned! 📋"
```

### Migration from Existing System

```bash
# Preview migration
kira migrate run --dry-run

# Review changes
kira migrate diff

# Execute migration
kira migrate run

# Validate after migration
kira validate

# Fix any issues
kira migrate fix
```

### Backup and Restore

```bash
# Create backup
make backup

# Or manually:
tar -czf backup-$(date +%Y%m%d).tar.gz vault/ artifacts/ logs/

# Restore from backup
make restore BACKUP=backups/kira-backup-20251008-143000.tar.gz

# Verify restoration
kira validate
kira doctor
```

### Plugin Management

```bash
# List available plugins
kira ext list

# Enable plugin
kira ext enable kira-inbox

# Disable plugin
kira ext disable kira-deadlines

# Plugin info
kira ext info kira-calendar

# Reload plugins
kira ext reload
```

### Diagnostics and Monitoring

```bash
# System diagnostics
kira doctor

# Monitor logs in real-time
kira monitor

# Specific component logs
kira monitor --component agent
kira monitor --component telegram

# Analyze logs
kira diag analyze --since 2025-10-01

# View audit trail
cat artifacts/audit/audit-$(date +%Y-%m-%d).jsonl | jq

# Export metrics
kira stats --export metrics.json
```

### Context Management (GTD)

```bash
# List contexts
kira context list

# Create context
kira context add "office" "Work at office"
kira context add "home" "Tasks at home"
kira context add "errands" "Out and about"

# Assign context to task
kira task update task-20251008-1234 --context office

# List tasks by context
kira context show office

# Context review
kira context review
```

---

## Docker Deployment Examples

### Basic Deployment

```bash
# Build image
make docker-build

# Start services
make docker-up

# Check status
docker ps

# View logs
docker logs -f kira-agent

# Stop services
make docker-down
```

### Docker Compose with Custom Config

```yaml
# docker-compose.override.yml
services:
  kira-agent:
    environment:
      - KIRA_LOG_LEVEL=DEBUG
      - ENABLE_RAG=true
      - MEMORY_MAX_EXCHANGES=10
    volumes:
      - ./custom-vault:/app/vault
```

```bash
# Start with override
docker compose -f compose.yaml -f docker-compose.override.yml up -d
```

### Production Deployment

```bash
# Build for production
docker build -t kira-agent:v0.1.0 .

# Tag for registry
docker tag kira-agent:v0.1.0 registry.example.com/kira-agent:v0.1.0

# Push to registry
docker push registry.example.com/kira-agent:v0.1.0

# Deploy on server
ssh server "docker pull registry.example.com/kira-agent:v0.1.0"
ssh server "docker compose up -d"
```

---

## JSON Output for Automation

Most commands support `--json` flag for machine-readable output:

```bash
# Task creation with JSON output
kira task add "Automated task" --json

# Output:
{
  "status": "success",
  "data": {
    "id": "task-20251008-1234",
    "title": "Automated task",
    "status": "todo",
    "created": "2025-10-08T12:34:56Z"
  }
}

# Task list as JSON
kira task list --json | jq '.data[] | select(.status=="todo")'

# Validate with JSON output
kira validate --json | jq '.errors | length'
```

---

## Environment Variable Examples

```bash
# Override vault path
export KIRA_VAULT_PATH=/custom/vault
kira task list

# Change timezone
export KIRA_DEFAULT_TZ=America/New_York
kira today

# Enable debug logging
export KIRA_LOG_LEVEL=DEBUG
kira agent start

# Set custom LLM provider
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your-key
kira agent start
```

---

## Performance Testing

```bash
# Benchmark task operations
time for i in {1..100}; do
  kira task add "Benchmark task $i" --json > /dev/null
done

# Validate large vault
time kira validate

# Test agent response time
time curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List all tasks", "execute": false}'
```

---

## Troubleshooting Commands

```bash
# Check vault integrity
kira validate --verbose

# Fix common issues
kira doctor --fix

# Rebuild indexes
kira vault reindex

# Clear cache
rm -rf .rag/ __pycache__/

# Reset entity
kira vault reset task-20251008-1234

# Export entity for debugging
kira vault export task-20251008-1234 --format json
```

---

## Integration Examples

### With Git Hooks

```bash
# .git/hooks/pre-commit
#!/bin/bash
# Validate vault before commit
poetry run kira validate || exit 1
```

### With Cron Jobs

```bash
# Daily backup and sync
0 23 * * * cd /path/to/kira && make backup
0 9 * * * cd /path/to/kira && poetry run kira calendar pull
0 18 * * * cd /path/to/kira && poetry run kira rollup daily
```

### With CI/CD

```yaml
# .github/workflows/validate.yml
name: Validate Vault
on: [push]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: poetry install
      - name: Validate vault
        run: poetry run kira validate
```

---

## Tips & Best Practices

### 1. Use Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias k='poetry run kira'
alias kt='poetry run kira task'
alias kn='poetry run kira note'
alias today='poetry run kira today'
```

### 2. Shell Completion

```bash
# Generate completion script
_kira_completion() {
  local IFS=$'\n'
  COMPREPLY=($(poetry run kira --help | grep '^\s*\w' | awk '{print $1}'))
}
complete -F _kira_completion kira
```

### 3. Regular Backups

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR=~/kira-backups
mkdir -p "$BACKUP_DIR"
cd /path/to/kira
make backup
mv backups/*.tar.gz "$BACKUP_DIR/"
# Keep only last 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
```

---

**More examples coming soon!**

For questions or contributions, see [README.md](../README.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).
