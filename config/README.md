# Kira Configuration Guide

## Overview

Kira uses a three-layer configuration system:

1. **Defaults** (`config/defaults.yaml`) - Base configuration with sensible defaults
2. **User Config** (`kira.yaml`) - Your customizations (overrides defaults)
3. **Environment Variables** (`KIRA_*`) - Runtime overrides (highest priority)

## Quick Start

### 1. Create User Config

Copy the example configuration:

```bash
cp config/kira.yaml.example kira.yaml
```

Edit `kira.yaml` to customize your setup. Common changes:

```yaml
vault:
  path: "/path/to/your/vault"

plugins:
  enabled:
    - kira-inbox
    - kira-calendar

adapters:
  telegram:
    enabled: true
```

### 2. Set Environment Variables

Copy the env example:

```bash
cp config/env.example .env
```

Edit `.env` with your secrets:

```bash
TELEGRAM_BOT_TOKEN=your_token_here
GCAL_CREDENTIALS_PATH=.credentials/gcal_credentials.json
```

**⚠️ Never commit `.env` to git!**

### 3. Configure Secrets (Optional)

For additional secrets:

```bash
mkdir -p .secrets
cp config/.secrets.example.json .secrets/keyring.json
```

Edit `.secrets/keyring.json` with your API keys and credentials.

**⚠️ Never commit `.secrets/` to git!**

## Configuration Priority

Settings are applied in this order (later overrides earlier):

```
defaults.yaml → kira.yaml → environment variables
```

### Example

```yaml
# defaults.yaml
sandbox:
  timeout_ms: 30000

# kira.yaml
sandbox:
  timeout_ms: 60000  # Overrides default

# Environment
KIRA_SANDBOX_TIMEOUT=45000  # Overrides both
```

Final value: `45000` (from environment variable)

## Configuration Options

### Core Settings

```yaml
core:
  timezone: "Europe/Brussels"  # Timezone for timestamps
  date_format: "%Y-%m-%d"
  datetime_format: "%Y-%m-%d %H:%M:%S"
```

**Environment:** `KIRA_TIMEZONE`

### Vault Settings

```yaml
vault:
  path: "vault"  # Path to vault directory
  inbox_folder: "inbox"
  processed_folder: "processed"
```

**Environment:** `KIRA_VAULT_PATH`

### Sandbox Settings

```yaml
sandbox:
  strategy: "subprocess"  # subprocess, thread, inline
  timeout_ms: 30000  # Plugin timeout (milliseconds)
  memory_limit_mb: 512  # Memory limit per plugin
  max_restarts: 3  # Max restart attempts
  restart_window_seconds: 300  # Restart counting window
```

**Environment:** `KIRA_SANDBOX_TIMEOUT`, `KIRA_SANDBOX_MEMORY_LIMIT`

### Plugin Settings

```yaml
plugins:
  enabled:
    - kira-inbox
    - kira-calendar
    - kira-deadlines
  
  inbox:
    confidence_threshold: 0.8  # 0.0 = ask always, 1.0 = never ask
    clarification_timeout_hours: 24.0
  
  calendar:
    default_calendar_id: "primary"
    sync_days_past: 7
    sync_days_future: 30
    timebox_default_minutes: 25
  
  deadlines:
    warning_days: [7, 3, 1]  # Warn N days before
    snooze_default_hours: 24
```

### Adapter Settings

```yaml
adapters:
  telegram:
    enabled: true
    mode: "bot"  # bot or userbot
    whitelist_chats: []  # Empty = all allowed
    max_message_length: 4096
  
  gcal:
    enabled: true
    credentials_path: ".credentials/gcal_credentials.json"
    timeout_seconds: 30
    max_results: 250
```

**Environment:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GCAL_CREDENTIALS_PATH`

### Logging Settings

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  path: "logs"
  console_output: true
  file_output: true
  rotation:
    max_bytes: 10485760  # 10 MB
    backup_count: 5
```

**Environment:** `KIRA_LOG_LEVEL`, `KIRA_LOG_PATH`

### Feature Flags

```yaml
features:
  timeboxing: true  # Auto-create calendar blocks
  clarifications: true  # Ask for confirmation
  auto_rollup: true  # Generate reports
  graph_validation: true  # Validate graph
  telemetry: true  # Structured logging
```

## Environment Variables

All environment variables are prefixed with `KIRA_`:

### Core

- `KIRA_VAULT_PATH` - Vault directory path
- `KIRA_TIMEZONE` - Default timezone
- `KIRA_CONFIG` - Config file path (default: kira.yaml)

### Logging

- `KIRA_LOG_LEVEL` - Log level (DEBUG/INFO/WARNING/ERROR)
- `KIRA_LOG_PATH` - Log directory path

### Sandbox

- `KIRA_SANDBOX_TIMEOUT` - Plugin timeout (milliseconds)
- `KIRA_SANDBOX_MEMORY_LIMIT` - Memory limit (MB)

### Adapters

- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Telegram chat ID
- `TELEGRAM_MODE` - Mode (bot/userbot)
- `GCAL_CREDENTIALS_PATH` - Google Calendar credentials
- `GCAL_TOKEN_PATH` - Google Calendar token
- `GCAL_CALENDAR_ID` - Calendar ID (default: primary)

### Security

- `KIRA_SECRETS_PATH` - Secrets file path
- `KIRA_ENCRYPTION_KEY` - Encryption key (base64)

### Development

- `KIRA_DEV_DEBUG` - Enable debug mode
- `KIRA_DEV_TEST_MODE` - Enable test mode
- `KIRA_DEV_MOCK_APIS` - Mock external APIs

## Accessing Configuration in Code

### From Python

```python
from kira.core.config import get_config

# Get singleton instance
config = get_config()

# Access with dot notation
vault_path = config.get("vault.path", "vault")
timeout = config.get("sandbox.timeout_ms", 30000)

# Get nested config
plugins = config.get("plugins.enabled", [])
telegram_enabled = config.get("adapters.telegram.enabled", False)

# Full config as dict
full_config = config.to_dict()
```

### From Plugins

```python
from kira.plugin_sdk import context

def activate(ctx: context.PluginContext):
    # Plugin config from manifest
    threshold = ctx.config.get("confidence_threshold", 0.8)
    
    # Global config (via SDK)
    vault_path = ctx.config.get("vault_path")
```

## Configuration Files Location

```
kira-project/
├── config/
│   ├── defaults.yaml          # System defaults (DO NOT EDIT)
│   ├── kira.yaml.example      # User config template
│   ├── env.example            # Environment vars template
│   └── .secrets.example.json  # Secrets template
├── kira.yaml                  # Your config (git ignored)
├── .env                       # Your env vars (git ignored)
└── .secrets/                  # Your secrets (git ignored)
    └── keyring.json
```

## Best Practices

### 1. Don't Edit `defaults.yaml`

Always override in `kira.yaml` instead:

```yaml
# ❌ Don't edit config/defaults.yaml
# ✅ Override in kira.yaml
sandbox:
  timeout_ms: 60000
```

### 2. Use Environment Variables for Secrets

```bash
# ✅ Good - in .env file
TELEGRAM_BOT_TOKEN=secret_token

# ❌ Bad - hardcoded in kira.yaml
adapters:
  telegram:
    token: "secret_token"  # DON'T DO THIS!
```

### 3. Keep `kira.yaml` Minimal

Only include settings you're changing:

```yaml
# ✅ Good - only overrides
vault:
  path: "/my/vault"

plugins:
  enabled:
    - kira-inbox

# ❌ Bad - too much copied from defaults
vault:
  path: "/my/vault"
  inbox_folder: "inbox"  # Already default
  processed_folder: "processed"  # Already default
  indexes_folder: "@Indexes"  # Already default
  # ... etc
```

### 4. Document Your Overrides

```yaml
# Use comments to explain why
sandbox:
  timeout_ms: 120000  # Increased for slow operations
  memory_limit_mb: 1024  # Large plugin needs more RAM
```

### 5. Use Version Control

```bash
# Commit
git add kira.yaml  # ✅ (if no secrets)
git add config/defaults.yaml  # ✅
git add config/*.example  # ✅

# Never commit
# .env
# .secrets/
# kira.yaml  # (if contains secrets)
```

## Troubleshooting

### Config Not Loading

```bash
# Check config path
python -c "from kira.core.config import get_config; print(get_config().to_dict())"

# Verify file exists
ls -la kira.yaml config/defaults.yaml

# Check permissions
stat kira.yaml
```

### Environment Variables Not Applied

```bash
# Test env var
export KIRA_VAULT_PATH=/tmp/test
python -c "from kira.core.config import get_config; print(get_config().get('vault.path'))"
```

### Priority Issues

If a setting isn't being applied, check the order:

1. Is the env var set? `env | grep KIRA_`
2. Is it in `kira.yaml`? `grep "setting" kira.yaml`
3. What's the default? `grep "setting" config/defaults.yaml`

### Validation Errors

```bash
# Validate config
kira validate

# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('kira.yaml'))"
```

## See Also

- [Configuration Documentation](../docs/configuration.md)
- [CLI Documentation](../docs/cli.md)
- [Plugin Development](../docs/sdk.md)

---

**Last Updated:** 2025-10-07

