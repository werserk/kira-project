# Kira CLI Documentation

## Overview

The Kira CLI provides a unified command-line interface for all Kira operations. All commands are invoked through the `kira` entry point and follow consistent patterns for flags, output, and error handling.

**Related ADRs:** ADR-010  
**Status:** Stable

## Installation

The CLI is available after installing Kira:

```bash
# From project root
pip install -e .

# Or using Poetry
poetry install

# Verify installation
kira --help
```

## General Usage

```bash
kira [COMMAND] [SUBCOMMAND] [OPTIONS]
```

### Global Flags

Available for all commands:

- `--verbose, -v` - Enable verbose output
- `--help, -h` - Show help message
- `--version` - Show Kira version

## Commands

### 1. `kira inbox`

Process items from the inbox folder.

**Synopsis:**

```bash
kira inbox [OPTIONS]
```

**Options:**

- `--vault PATH` - Path to vault (default: from config)
- `--dry-run` - Preview without making changes
- `--max-items N` - Limit items to process (default: 100)
- `--verbose` - Show detailed processing logs

**Examples:**

```bash
# Process inbox with default settings
kira inbox

# Dry run to preview what would be processed
kira inbox --dry-run --verbose

# Process only first 10 items
kira inbox --max-items 10

# Use custom vault path
kira inbox --vault /path/to/vault
```

**Output:**

```
📥 Processing inbox...
✅ Scanned: 5 items
✅ Processed: 5 items
✅ Failed: 0 items
⏱️  Duration: 1.2s
```

### 2. `kira calendar`

Synchronize calendar events with Google Calendar.

**Synopsis:**

```bash
kira calendar {pull|push} [OPTIONS]
```

**Subcommands:**

- `pull` - Pull events from Google Calendar to Vault
- `push` - Push events from Vault to Google Calendar

**Options:**

- `--calendar-id ID` - Google Calendar ID (default: primary)
- `--days N` - Number of days to sync (default: 30)
- `--dry-run` - Preview without making changes
- `--verbose` - Show detailed sync logs

**Examples:**

```bash
# Pull events from Google Calendar
kira calendar pull

# Pull next 7 days
kira calendar pull --days 7

# Push events to Google Calendar
kira calendar push

# Dry run push
kira calendar push --dry-run --verbose

# Use specific calendar
kira calendar pull --calendar-id work@example.com
```

**Output:**

```
📅 Pulling events from Google Calendar...
✅ Fetched: 15 events
✅ Created: 3 new entities
✅ Updated: 2 existing entities
✅ Skipped: 10 unchanged
⏱️  Duration: 2.5s
```

### 3. `kira rollup`

Generate daily or weekly rollup reports.

**Synopsis:**

```bash
kira rollup {daily|weekly} [OPTIONS]
```

**Subcommands:**

- `daily` - Generate daily rollup
- `weekly` - Generate weekly rollup

**Options:**

- `--date DATE` - Date for rollup (default: today, format: YYYY-MM-DD)
- `--week WEEK` - Week number for weekly rollup (format: YYYY-Wnn)
- `--output PATH` - Custom output path
- `--verbose` - Show detailed generation logs

**Examples:**

```bash
# Generate today's rollup
kira rollup daily

# Generate rollup for specific date
kira rollup daily --date 2025-01-07

# Generate this week's rollup
kira rollup weekly

# Generate specific week's rollup
kira rollup weekly --week 2025-W01

# Custom output location
kira rollup daily --output /path/to/rollups/
```

**Output:**

```
📊 Generating daily rollup for 2025-01-07...
✅ Tasks completed: 5
✅ Events attended: 3
✅ Notes created: 2
✅ Rollup saved: vault/rollups/daily-20250107.md
⏱️  Duration: 0.8s
```

### 4. `kira vault`

Manage Vault structure and entities.

**Synopsis:**

```bash
kira vault {init|validate|info|new|schemas} [OPTIONS]
```

**Subcommands:**

- `init` - Initialize new Vault
- `validate` - Validate Vault structure and entities
- `info` - Show Vault statistics
- `new` - Create new entity
- `schemas` - Manage entity schemas

**Options (varies by subcommand):**

**init:**
- `--path PATH` - Path for new vault (default: current directory)
- `--template NAME` - Template to use (default: minimal)

**validate:**
- `--type TYPE` - Validate specific entity type only
- `--fix` - Attempt to fix validation errors (with confirmation)

**new:**
- `--type TYPE` - Entity type (task, note, event, etc.)
- `--title TITLE` - Entity title
- `--template PATH` - Use custom template

**schemas:**
- `--list` - List available schemas
- `--show TYPE` - Show schema for entity type
- `--validate-schema PATH` - Validate schema file

**Examples:**

```bash
# Initialize new Vault
kira vault init --path /path/to/vault

# Validate entire Vault
kira vault validate --verbose

# Validate only tasks
kira vault validate --type task

# Show Vault statistics
kira vault info

# Create new task
kira vault new --type task --title "Fix bug in authentication"

# Create new note
kira vault new --type note --title "Meeting notes"

# List available schemas
kira vault schemas --list

# Show task schema
kira vault schemas --show task

# Validate custom schema
kira vault schemas --validate-schema /path/to/schema.json
```

**Output (info):**

```
📊 Vault Statistics

Entities:
  Tasks: 42
  Notes: 18
  Events: 25
  Total: 85

Status:
  ✅ Valid: 83
  ⚠️  Warnings: 2
  ❌ Errors: 0

Links:
  Total: 156
  Broken: 0
  Orphaned entities: 3

Last validated: 2025-01-07 14:30:00
```

### 5. `kira ext`

Manage plugins and extensions.

**Synopsis:**

```bash
kira ext {list|info|enable|disable|install} [OPTIONS]
```

**Subcommands:**

- `list` - List all available plugins
- `info` - Show plugin information
- `enable` - Enable plugin
- `disable` - Disable plugin
- `install` - Install external plugin

**Options:**

- `NAME` - Plugin name (for info/enable/disable)
- `--all` - Show all plugins including disabled (for list)
- `--json` - Output in JSON format
- `--verbose` - Show detailed information

**Examples:**

```bash
# List enabled plugins
kira ext list

# List all plugins
kira ext list --all

# Show plugin information
kira ext info kira-inbox

# Enable plugin
kira ext enable kira-calendar

# Disable plugin
kira ext disable kira-code

# Install external plugin
kira ext install /path/to/plugin/
```

**Output (list):**

```
📦 Installed Plugins

kira-inbox v1.0.0 ✅ enabled
  Normalizes incoming messages into typed entities

kira-calendar v1.0.0 ✅ enabled
  Synchronizes with Google Calendar

kira-code v1.0.0 ⚪ disabled
  Code analysis and indexing

kira-deadlines v1.0.0 ✅ enabled
  Deadline tracking and notifications

Total: 4 plugins (3 enabled, 1 disabled)
```

### 6. `kira code`

Code analysis and search (requires kira-code plugin).

**Synopsis:**

```bash
kira code {analyze|index|search} [OPTIONS]
```

**Subcommands:**

- `analyze` - Analyze code structure
- `index` - Build code search index
- `search` - Search code

**Options:**

- `--path PATH` - Path to analyze/index (default: current directory)
- `QUERY` - Search query (for search)
- `--lang LANGUAGE` - Filter by language
- `--verbose` - Show detailed output

**Examples:**

```bash
# Analyze code
kira code analyze

# Build search index
kira code index --path /path/to/code

# Search code
kira code search "function_name"

# Search Python only
kira code search "class" --lang python
```

### 7. `kira diag`

Diagnostics and troubleshooting.

**Synopsis:**

```bash
kira diag {tail|status|logs} [OPTIONS]
```

**Subcommands:**

- `tail` - Tail structured logs
- `status` - Show system status
- `logs` - Export logs for analysis

**Options:**

- `--component NAME` - Filter by component (core/adapter/plugin/pipeline)
- `--trace-id ID` - Filter by trace ID
- `--level LEVEL` - Filter by log level (debug/info/warning/error)
- `--since DURATION` - Show logs since duration (e.g., "1h", "30m")
- `--follow, -f` - Follow log output

**Examples:**

```bash
# Tail all logs
kira diag tail

# Tail core component logs
kira diag tail --component core

# Follow logs in real-time
kira diag tail --follow

# Show logs for specific trace
kira diag tail --trace-id abc-123-def

# Show errors from last hour
kira diag tail --level error --since 1h

# Show system status
kira diag status

# Export logs
kira diag logs --since 24h --output /tmp/kira-logs.jsonl
```

**Output (status):**

```
🔧 System Status

Components:
  ✅ Core: Running
  ✅ Event Bus: Active (42 subscriptions)
  ✅ Scheduler: Active (5 jobs)
  ✅ Plugins: 3/4 active

Recent Activity:
  Events published: 156 (last hour)
  Jobs executed: 12 (last hour)
  Errors: 0 (last hour)

Health: ✅ All systems operational
```

### 8. `kira validate`

Validate configuration and manifests.

**Synopsis:**

```bash
kira validate [OPTIONS]
```

**Options:**

- `--config PATH` - Path to config file (default: kira.yaml)
- `--manifest PATH` - Validate specific plugin manifest
- `--all` - Validate all manifests in project
- `--verbose` - Show detailed validation output

**Examples:**

```bash
# Validate configuration
kira validate

# Validate all plugin manifests
kira validate --all

# Validate specific manifest
kira validate --manifest src/kira/plugins/inbox/kira-plugin.json

# Custom config path
kira validate --config /path/to/config.yaml
```

**Output:**

```
✅ Configuration valid: kira.yaml
✅ Manifest valid: kira-inbox
✅ Manifest valid: kira-calendar
✅ Manifest valid: kira-deadlines
✅ Manifest valid: kira-code

All validations passed! 🎉
```

## Makefile Integration

Common workflows are available as Make targets:

```bash
# Inbox operations
make inbox                # Process inbox
make inbox-dry-run       # Preview inbox processing

# Calendar operations
make calendar-pull       # Pull from Google Calendar
make calendar-push       # Push to Google Calendar

# Rollup operations
make rollup-daily        # Generate daily rollup
make rollup-weekly       # Generate weekly rollup

# Vault operations
make vault-init          # Initialize Vault
make vault-validate      # Validate Vault
make vault-info          # Show Vault info

# Extension management
make ext-list            # List plugins
make ext-enable NAME=... # Enable plugin
make ext-disable NAME=...# Disable plugin

# Validation
make validate            # Validate everything

# Help
make help                # Show available commands
```

## Exit Codes

Kira CLI uses standard exit codes:

- `0` - Success
- `1` - General error
- `2` - Command-line usage error
- `3` - Configuration error
- `4` - Validation error
- `5` - Network/API error

## Environment Variables

- `KIRA_VAULT_PATH` - Override vault path
- `KIRA_CONFIG` - Override config file location
- `KIRA_LOG_LEVEL` - Set log level (DEBUG/INFO/WARNING/ERROR)
- `KIRA_GCAL_CREDENTIALS` - Path to Google Calendar credentials

## Configuration

CLI behavior can be configured in `kira.yaml`:

```yaml
vault:
  path: /path/to/vault
  
logging:
  level: INFO
  path: logs/

plugins:
  enabled:
    - kira-inbox
    - kira-calendar
    - kira-deadlines

calendar:
  default_calendar_id: primary
  sync_days: 30

inbox:
  max_items_per_run: 100
```

## Structured Output

Many commands support `--json` flag for machine-readable output:

```bash
# JSON output
kira ext list --json
```

```json
{
  "plugins": [
    {
      "name": "kira-inbox",
      "version": "1.0.0",
      "enabled": true,
      "description": "Normalizes incoming messages"
    }
  ]
}
```

## Error Handling

Errors are displayed with context and suggestions:

```
❌ Error: Vault not found at /path/to/vault

Suggestions:
  • Initialize a new vault: kira vault init --path /path/to/vault
  • Check your configuration: kira validate
  • Specify vault path: kira inbox --vault /correct/path

For more help: kira --help
```

## Debugging

Enable verbose output for troubleshooting:

```bash
# Verbose output
kira inbox --verbose

# Debug level logging
KIRA_LOG_LEVEL=DEBUG kira inbox

# Tail logs while running command (in another terminal)
kira diag tail --follow
```

## Shell Completion

Generate shell completion scripts:

```bash
# Bash
kira completion bash > /etc/bash_completion.d/kira

# Zsh
kira completion zsh > "${fpath[1]}/_kira"

# Fish
kira completion fish > ~/.config/fish/completions/kira.fish
```

## See Also

- [Configuration Documentation](configuration.md)
- [Plugin SDK Documentation](sdk.md)
- [Makefile Reference](../Makefile)
- [ADR-010: CLI & Make](adr/ADR-010-cli-make-canonical-interface.md)

---

**Last Updated:** 2025-10-07  
**CLI Version:** 1.0.0
