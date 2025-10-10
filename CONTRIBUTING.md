# Contributing to Kira

**Thank you for your interest in contributing to Kira!**

This document outlines the technical standards, architectural principles, and development workflow for the Kira project. All contributors must adhere to these guidelines to maintain code quality and system integrity.

---

## Table of Contents

1. [Project Architecture](#project-architecture)
2. [Code Organization](#code-organization)
3. [Naming Conventions](#naming-conventions)
4. [Configuration Management](#configuration-management)
5. [Testing Requirements](#testing-requirements)
6. [Code Quality Standards](#code-quality-standards)
7. [Git Workflow](#git-workflow)
8. [Pull Request Process](#pull-request-process)
9. [Documentation Requirements](#documentation-requirements)

---

## Project Architecture

### Core Principles

Kira follows a **layered architecture** with strict separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Ingress Layer (Adapters)                 │
│  • Telegram, CLI, HTTP API, Google Calendar                 │
│  • Normalize external data into internal events             │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Event Bus (Core)                         │
│  • Idempotent event processing                              │
│  • At-least-once delivery semantics                         │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic                           │
│  • Task FSM, Validation, Plugins                            │
│  • Enforce business rules before writes                     │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Host API (Single Writer)                 │
│  • ALL writes go through HostAPI                            │
│  • Atomic operations with file locks                        │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Vault (Storage)                          │
│  • Plain markdown + YAML frontmatter                        │
│  • 100% Obsidian-compatible                                 │
└─────────────────────────────────────────────────────────────┘
```

### Architectural Decision Records (ADRs)

Kira documents **every major architectural decision**. Before making significant changes:

1. **Read existing ADRs** in `docs/architecture/`
2. **Understand the rationale** behind current design
3. **Create a new ADR** if proposing architectural changes

**Key ADRs:**
- **ADR-001**: Single Writer Pattern - All writes through HostAPI
- **ADR-002**: YAML Frontmatter Schema - Entity metadata format
- **ADR-003**: Event Idempotency - Exactly-once processing
- **ADR-005**: UTC Time Discipline - All timestamps in UTC

**Violation of ADRs is NOT permitted without team discussion.**

---

## Code Organization

### Directory Structure

```
kira-project/
├── src/kira/                    # Source code (production)
│   ├── core/                    # Core business logic
│   │   ├── host.py             # HostAPI - single writer
│   │   ├── task_fsm.py         # Task state machine
│   │   ├── validation.py       # Schema validation
│   │   └── events.py           # Event bus
│   ├── adapters/                # External system integrations
│   │   ├── telegram/           # Telegram bot adapter
│   │   ├── gcal/               # Google Calendar adapter
│   │   ├── llm/                # LLM provider adapters
│   │   └── filesystem/         # File system watcher
│   ├── agent/                   # AI agent (LLM-based)
│   │   ├── executor.py         # Agent execution engine
│   │   ├── tools.py            # Tool registry
│   │   └── config.py           # Agent configuration
│   ├── cli/                     # CLI commands
│   ├── plugins/                 # Built-in plugins
│   ├── config/                  # Configuration management
│   │   └── settings.py         # Centralized Settings
│   └── storage/                 # Vault storage layer
├── tests/                       # Test suite
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── docs/                        # Documentation
│   ├── architecture/           # ADRs and design docs
│   ├── guides/                 # User guides
│   └── reports/                # Reports (audits, completions)
├── config/                      # Configuration templates
│   ├── kira.yaml.example       # YAML config template
│   └── README.md               # Config documentation
├── vault/                       # User data (not in git)
├── .env.example                 # Environment template
└── pyproject.toml              # Python dependencies
```

### File Placement Rules

| Type | Location | Example |
|------|----------|---------|
| **Core logic** | `src/kira/core/` | `task_fsm.py`, `validation.py` |
| **External adapters** | `src/kira/adapters/<name>/` | `telegram/adapter.py` |
| **CLI commands** | `src/kira/cli/` | `kira_task.py` |
| **Built-in plugins** | `src/kira/plugins/` | `inbox_plugin.py` |
| **Configuration** | `src/kira/config/` | `settings.py` |
| **Unit tests** | `tests/unit/` | `test_task_fsm.py` |
| **Integration tests** | `tests/integration/` | `test_telegram_adapter_integration.py` |
| **Architecture docs** | `docs/architecture/` | `telegram-integration.md` |
| **User guides** | `docs/guides/` | `quickstart.md` |
| **Reports** | `docs/reports/` | `001-alpha-readiness-audit.md` |

**❌ DO NOT:**
- Place business logic in adapters
- Create files in project root (except standard files like README, LICENSE)
- Mix test code with production code

**✅ DO:**
- Keep adapters thin (orchestration only)
- Put business rules in `core/`
- Use subdirectories for complex modules

---

## Naming Conventions

### Python Code

#### Files
```python
# ✅ CORRECT
task_fsm.py              # snake_case for modules
telegram_adapter.py      # descriptive names
test_task_fsm.py         # test_ prefix for tests

# ❌ INCORRECT
TaskFSM.py              # PascalCase not allowed
telegram.py             # too generic
task_fsm_test.py        # wrong test naming
```

#### Classes
```python
# ✅ CORRECT
class TaskStateMachine:     # PascalCase
class TelegramAdapter:      # Clear, descriptive
class HostAPI:              # Abbreviations OK if clear

# ❌ INCORRECT
class task_fsm:            # snake_case not allowed
class Adapter:             # too generic
class TGAdapter:           # unclear abbreviation
```

#### Functions/Methods
```python
# ✅ CORRECT
def create_entity():        # snake_case, verb prefix
def validate_task():        # descriptive action
def _internal_helper():     # leading underscore for private

# ❌ INCORRECT
def CreateEntity():        # PascalCase not allowed
def entity():              # missing verb
def __dunder__():          # double underscore reserved
```

#### Variables
```python
# ✅ CORRECT
task_id = "task-123"           # snake_case
max_retries = 3                # descriptive
entity_type = "task"           # clear intent

# ❌ INCORRECT
taskId = "task-123"            # camelCase not allowed
x = 3                          # non-descriptive
MAX_RETRIES = 3                # constants are UPPER_CASE
```

#### Constants
```python
# ✅ CORRECT
MAX_TOOL_CALLS = 10            # UPPER_CASE
DEFAULT_TIMEOUT = 60.0         # with underscores
API_BASE_URL = "https://..."   # clear purpose

# ❌ INCORRECT
max_tool_calls = 10            # lowercase not allowed
MaxToolCalls = 10              # PascalCase not allowed
```

### File System

#### Entity Files (Vault)
```
# ✅ CORRECT
task-20251009-1234.md          # type-YYYYMMDD-HHMM.md
note-20251009-1500.md          # ISO-8601 date format
event-20251009-0900.md         # hyphen-separated

# ❌ INCORRECT
task_20251009_1234.md          # underscores not allowed
task-2025-10-09-12-34.md       # too many hyphens
my-task.md                     # no timestamp
```

#### Documentation
```
# ✅ CORRECT
docs/architecture/telegram-integration.md
docs/reports/001-alpha-readiness-audit.md
docs/guides/quickstart.md

# ❌ INCORRECT
docs/TelegramIntegration.md    # PascalCase not allowed
docs/audit.md                  # no number prefix in reports/
TelegramDoc.md                 # wrong location
```

### Environment Variables

```bash
# ✅ CORRECT - Core settings (KIRA_ prefix)
KIRA_VAULT_PATH=vault
KIRA_DEFAULT_TZ=UTC
KIRA_TELEGRAM_ENABLED=true

# ✅ CORRECT - External services (no prefix)
TELEGRAM_BOT_TOKEN=xxx
ANTHROPIC_API_KEY=xxx
OPENROUTER_API_KEY=xxx

# ❌ INCORRECT
vaultPath=xxx                  # camelCase not allowed
VAULT_PATH=xxx                 # missing KIRA_ prefix for core
KIRA_TELEGRAM_BOT_TOKEN=xxx    # external service with prefix
```

**Rule:**
- Core Kira settings: `KIRA_` prefix
- External service credentials: No prefix
- All uppercase with underscores

---

## Configuration Management

### Single Source of Truth

**ALL configuration MUST go through `Settings` class.**

```python
# ✅ CORRECT - Use Settings
from kira.config.settings import load_settings

settings = load_settings()
bot_token = settings.telegram_bot_token

# ❌ INCORRECT - Direct env access
import os
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")  # NOT ALLOWED
```

### Adding New Configuration

When adding a new configuration parameter:

1. **Add field to `Settings` dataclass** (`src/kira/config/settings.py`)
   ```python
   # Add to Settings class
   new_parameter: str = "default_value"
   ```

2. **Update `Settings.from_env()` method**
   ```python
   # In from_env() method
   new_parameter=os.environ.get("KIRA_NEW_PARAMETER", "default"),
   ```

3. **Update `.env.example`**
   ```bash
   # Add to .env.example
   KIRA_NEW_PARAMETER=default_value
   ```

4. **Update documentation**
   - Add to `config/README.md`
   - Add to `QUICKSTART.md` if user-facing

5. **Add tests**
   ```python
   # In tests/unit/test_config_settings.py
   def test_new_parameter():
       settings = Settings(
           vault_path=Path("vault"),
           new_parameter="test_value"
       )
       assert settings.new_parameter == "test_value"
   ```

**Never bypass this process!**

---

## Testing Requirements

### Coverage Requirements

- **Minimum coverage:** 95%
- **Core modules:** 100% coverage required
- **Adapters:** 90% minimum
- **CLI:** 85% minimum

### Test Organization

```
tests/
├── unit/                           # Fast, isolated tests
│   ├── test_<module>.py           # One test file per module
│   └── fixtures/                  # Shared fixtures
└── integration/                    # Slower, end-to-end tests
    ├── adapters/                  # Adapter integration
    ├── cli/                       # CLI command tests
    └── core/                      # Core integration
```

### Test Naming

```python
# ✅ CORRECT
def test_create_entity_success():           # test_<what>_<scenario>
def test_task_transition_invalid_state():   # descriptive
def test_validation_missing_required_field():

# ❌ INCORRECT
def test_1():                               # non-descriptive
def testCreateEntity():                     # camelCase
def test():                                 # too generic
```

### Test Structure

**Use AAA pattern (Arrange-Act-Assert):**

```python
def test_create_task():
    # Arrange
    host_api = create_host_api(tmp_path / "vault")
    task_data = {
        "title": "Test Task",
        "status": "todo"
    }

    # Act
    entity = host_api.create_entity("task", task_data)

    # Assert
    assert entity.id.startswith("task-")
    assert entity.metadata["title"] == "Test Task"
    assert entity.metadata["status"] == "todo"
```

### Required Tests

When adding new functionality, you MUST provide:

1. **Unit tests** - Test function/class in isolation
2. **Integration tests** - Test interaction with system
3. **Edge cases** - Test error conditions
4. **Regression tests** - If fixing a bug

**Example:**

```python
# For new function: validate_task()

# Unit test
def test_validate_task_valid_data():
    """Valid task data passes validation."""
    # ... test happy path

def test_validate_task_missing_title():
    """Task without title raises ValidationError."""
    # ... test error case

# Integration test
def test_create_task_with_validation():
    """Task creation validates through entire stack."""
    # ... test full workflow
```

### Running Tests

```bash
# All tests
poetry run pytest tests/

# Unit tests only (fast)
poetry run pytest tests/unit/

# Specific test file
poetry run pytest tests/unit/test_task_fsm.py

# With coverage
poetry run pytest --cov=src/kira --cov-report=html

# Stop on first failure
poetry run pytest -x
```

---

## Code Quality Standards

### Linting and Formatting

All code MUST pass these checks before commit:

```bash
# Format with Black
poetry run black src/ tests/

# Lint with Ruff
poetry run ruff check src/ tests/

# Type check with Mypy
poetry run mypy src/

# Run all checks
make lint
```

### Pre-commit Hooks

**Install pre-commit hooks:**

```bash
poetry run pre-commit install
```

Hooks will automatically run on `git commit`:
- Black formatting
- Ruff linting
- Mypy type checking
- Trailing whitespace removal

**Do not bypass pre-commit hooks** with `--no-verify`!

### Type Annotations

**All functions MUST have type annotations:**

```python
# ✅ CORRECT
def create_entity(
    entity_type: str,
    data: dict[str, Any],
    *,
    validate: bool = True
) -> Entity:
    """Create an entity in the vault.

    Parameters
    ----------
    entity_type
        Type of entity (task, note, event)
    data
        Entity metadata
    validate
        Whether to validate before creation

    Returns
    -------
    Entity
        Created entity

    Raises
    ------
    ValidationError
        If data is invalid
    """
    ...

# ❌ INCORRECT - No type hints
def create_entity(entity_type, data, validate=True):
    ...
```

### Docstrings

**Use NumPy style docstrings:**

```python
def function_name(param1: int, param2: str) -> bool:
    """Short one-line summary.

    Longer description if needed. Explain what the function does,
    not how it does it.

    Parameters
    ----------
    param1
        Description of param1
    param2
        Description of param2

    Returns
    -------
    bool
        Description of return value

    Raises
    ------
    ValueError
        When param1 is negative

    Examples
    --------
    >>> function_name(42, "test")
    True
    """
    ...
```

### Error Handling

```python
# ✅ CORRECT - Specific exceptions
def read_entity(entity_id: str) -> Entity:
    if not entity_id:
        raise ValueError("entity_id cannot be empty")

    path = self.vault_path / entity_type / f"{entity_id}.md"
    if not path.exists():
        raise EntityNotFoundError(f"Entity {entity_id} not found")

    try:
        return self._parse_entity(path)
    except yaml.YAMLError as e:
        raise EntityParseError(f"Failed to parse {entity_id}") from e

# ❌ INCORRECT - Bare except
def read_entity(entity_id):
    try:
        # ...
    except:  # Too broad!
        return None  # Swallows all errors!
```

**Rules:**
1. Catch specific exceptions
2. Use custom exception classes
3. Chain exceptions with `from`
4. Don't swallow errors silently

---

## Logging Standards

### Loguru Integration

Kira uses **loguru** for structured logging with precise timing instrumentation. This enables performance optimization by tracking time between processes.

**Key logging flow:** NL (Telegram) → LLM (OpenRouter, LangGraph) → DB (Markdown, Vault)

### Configuration

**Initialize loguru at application startup:**

```python
from kira.observability.loguru_config import configure_loguru
from pathlib import Path

# Configure once at startup
configure_loguru(
    log_dir=Path("logs"),
    level="INFO",
    enable_timing_logs=True  # Separate timing.jsonl file
)
```

### Component-Specific Loggers

**Always use component-bound loggers:**

```python
# ✅ CORRECT - Component-specific logger
from kira.observability.loguru_config import get_logger

telegram_logger = get_logger("telegram")
llm_logger = get_logger("langgraph")
vault_logger = get_logger("vault")
agent_logger = get_logger("agent")
pipeline_logger = get_logger("pipeline")

# Log with automatic component filtering
telegram_logger.info("Message received", trace_id=trace_id, chat_id=123)

# ❌ INCORRECT - Direct loguru import
from loguru import logger
logger.info("Message received")  # No component filtering!
```

**Available components:**
- `telegram` - Telegram adapter operations
- `langgraph` - LLM/AI processing (OpenRouter, Anthropic, etc.)
- `vault` - Storage operations (markdown files)
- `agent` - Agent executor and orchestration
- `pipeline` - Pipeline operations (inbox, sync, rollup)

### Timing Instrumentation

**Use timing context for performance-critical operations:**

```python
# ✅ CORRECT - Timing context
from kira.observability.loguru_config import timing_context

def process_message(message: str, trace_id: str):
    with timing_context(
        "telegram_to_llm",
        component="agent",
        trace_id=trace_id,
        message_length=len(message),
    ) as ctx:
        # Do work here
        result = llm.generate(message)

        # Add runtime metrics to context
        ctx["tokens_used"] = result.tokens
        ctx["model"] = result.model

        return result
```

**Manual timing for fine-grained control:**

```python
from kira.observability.loguru_config import log_process_start, log_process_end

def complex_operation(trace_id: str):
    start_ns = log_process_start(
        "vault_write",
        component="vault",
        trace_id=trace_id,
        file_size=1024,
    )

    # Do work
    write_to_disk(data)

    duration_ms = log_process_end(
        "vault_write",
        start_ns,
        component="vault",
        trace_id=trace_id,
        success=True,
    )
```

**End-to-end timing with TimingLogger:**

```python
from kira.observability.loguru_config import get_timing_logger

def handle_request(trace_id: str):
    timing = get_timing_logger(trace_id=trace_id, component="agent")

    timing.start("telegram_ingestion")
    ingest_message()
    timing.end("telegram_ingestion", message_size=512)

    timing.start("llm_processing")
    response = call_llm()
    timing.end("llm_processing", tokens=150, model="gpt-4")

    timing.start("vault_write")
    save_to_vault()
    timing.end("vault_write", entity_type="task")

    # Log summary with all timings
    timing.log_summary()
```

### Logging Best Practices

**1. Always include trace_id for correlation:**

```python
# ✅ CORRECT
logger.info("Processing request", trace_id=trace_id, user_id=123)

# ❌ INCORRECT
logger.info("Processing request")  # Can't correlate across services!
```

**2. Use structured logging (key-value pairs):**

```python
# ✅ CORRECT - Structured
logger.info(
    "LLM generation completed",
    trace_id=trace_id,
    provider="openrouter",
    model="gpt-4",
    tokens=150,
    duration_ms=1250,
)

# ❌ INCORRECT - String interpolation
logger.info(f"LLM generation completed: {provider}, {tokens} tokens")
```

**3. Choose appropriate log levels:**

```python
# DEBUG - Detailed diagnostic information
logger.debug("Cache hit", key="task-123", ttl=300)

# INFO - General informational messages
logger.info("Task created", task_id="task-123", title="My Task")

# WARNING - Something unexpected but recoverable
logger.warning("Rate limit approached", remaining=5, limit=100)

# ERROR - Error occurred but system continues
logger.error("LLM request failed", error=str(e), provider="openrouter")

# CRITICAL - System failure, immediate attention needed
logger.critical("Vault corruption detected", path=str(vault_path))
```

**4. Log at key integration points:**

Required logging points in the business logic flow:

```python
# Telegram adapter - message ingestion
telegram_logger.info("Message received from Telegram", trace_id=trace_id, chat_id=123)

# LLM router - before/after API call
llm_logger.info("LLM request started", provider="openrouter", trace_id=trace_id)
llm_logger.info("LLM request completed", tokens=150, duration_ms=1200)

# Vault storage - entity operations
vault_logger.info("Entity upserted", entity_type="task", entity_id="task-123")

# Agent executor - end-to-end result
agent_logger.info("Request completed", trace_id=trace_id, success=True)
```

**5. Never log sensitive data:**

```python
# ✅ CORRECT
logger.info("User authenticated", user_id=hash(username))

# ❌ INCORRECT
logger.info("User authenticated", password=password, api_key=key)
```

### Log File Organization

Loguru automatically creates component-specific log files:

```
logs/
├── kira.jsonl          # Main application log (all components)
├── timing.jsonl        # Performance timing data
├── telegram.jsonl      # Telegram adapter only
├── langgraph.jsonl     # LLM operations only
├── vault.jsonl         # Storage operations only
├── agent.jsonl         # Agent executor only
└── pipeline.jsonl      # Pipeline operations only
```

**Benefits:**
- **Filtering**: Easy to grep specific component
- **Performance**: Analyze timing.jsonl for bottlenecks
- **Debugging**: Focus on one layer of the stack
- **Monitoring**: Alert on component-specific patterns

### Analyzing Timing Logs

**Find slowest operations:**

```bash
# Top 10 slowest operations
jq -r 'select(.extra.timing == true) | "\(.extra.duration_ms)ms - \(.extra.operation)"' logs/timing.jsonl | sort -rn | head -10

# Average duration by operation
jq -r 'select(.extra.timing == true) | "\(.extra.operation) \(.extra.duration_ms)"' logs/timing.jsonl | awk '{sum[$1]+=$2; count[$1]++} END {for (op in sum) print sum[op]/count[op] "ms -", op}' | sort -rn
```

**Trace specific request:**

```bash
# Follow trace_id through entire stack
grep "trace_id.*abc-123" logs/kira.jsonl | jq .

# Timing breakdown for trace
grep "trace_id.*abc-123" logs/timing.jsonl | jq -r '"\(.extra.operation): \(.extra.duration_ms)ms"'
```

### Migration from Legacy Logging

**Old pattern (deprecated):**

```python
# ❌ OLD - Don't use
from kira.observability.logging import StructuredLogger

logger = StructuredLogger("kira", log_file=Path("logs/app.jsonl"))
logger.log("INFO", "event_type", "message", correlation_id=uid)
```

**New pattern:**

```python
# ✅ NEW - Use this
from kira.observability.loguru_config import get_logger

logger = get_logger("agent")
logger.info("message", trace_id=trace_id, entity_id=uid)
```

**Legacy StructuredLogger is still available for backward compatibility but should not be used in new code.**

---

## Git Workflow

### Branch Naming

```bash
# ✅ CORRECT
feature/add-notion-adapter
bugfix/telegram-timezone-issue
refactor/unified-config
docs/update-contributing-guide

# ❌ INCORRECT
new-feature              # no type prefix
fix                      # too vague
john-branch              # no personal names
```

**Format:** `<type>/<short-description>`

**Types:**
- `feature/` - New functionality
- `bugfix/` - Bug fixes
- `refactor/` - Code improvements (no behavior change)
- `docs/` - Documentation only
- `test/` - Test additions/improvements

### Commit Messages

**Format:**

```
<type>: <subject>

<body>

<footer>
```

**Example:**

```
feat: Add Google Calendar two-way sync

Implements bidirectional synchronization with Google Calendar API.
Uses last-writer-wins conflict resolution strategy.

Closes #123
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `docs:` - Documentation
- `test:` - Test changes
- `chore:` - Maintenance

**Rules:**
1. Subject line ≤ 72 characters
2. Imperative mood ("Add" not "Added")
3. No period at end of subject
4. Body explains "why", not "what"

---

## Pull Request Process

### Before Opening PR

**Checklist:**

- [ ] All tests pass locally (`poetry run pytest`)
- [ ] Code formatted (`poetry run black .`)
- [ ] Linter clean (`poetry run ruff check .`)
- [ ] Type checks pass (`poetry run mypy src/`)
- [ ] Coverage ≥ 95% (`poetry run pytest --cov`)
- [ ] Documentation updated
- [ ] `CHANGELOG.md` updated (if user-facing)

### PR Title

Follow commit message format:

```
feat: Add Notion adapter integration
fix: Correct timezone handling in briefings
refactor: Unify configuration architecture
```

### PR Description Template

```markdown
## What

Brief description of changes.

## Why

Why is this change necessary?

## How

How does this change work?

## Testing

How was this tested?

## Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] ADR created (if architectural change)
- [ ] Backward compatible (or migration guide provided)

## Related Issues

Closes #123
Related to #456
```

### Review Requirements

- **At least 1 approval** required
- **All CI checks must pass**
- **No merge conflicts**
- **Branch up-to-date with main**

### CI Checks

```yaml
# .github/workflows/ci.yml

jobs:
  lint:
    - black --check
    - ruff check
    - mypy src/

  test:
    - pytest tests/unit/
    - pytest tests/integration/

  coverage:
    - pytest --cov --cov-fail-under=95
```

**All checks MUST pass before merge.**

---

## Documentation Requirements

### Code Documentation

1. **Module docstring** - Purpose of module
2. **Class docstring** - What the class does
3. **Method docstring** - Parameters, returns, raises
4. **Inline comments** - Complex logic only

### External Documentation

When adding features, update:

1. **README.md** - If user-facing
2. **QUICKSTART.md** - If affects setup
3. **Module README** - If adapter/plugin
4. **CHANGELOG.md** - Always for releases

### ADRs (Architecture Decision Records)

**When to create:**
- Changing architectural patterns
- Adding new major dependencies
- Modifying core abstractions
- Performance trade-offs

**ADR Template:**

```markdown
# ADR-XXX: Title

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated

## Context

What is the problem we're solving?

## Decision

What did we decide?

## Consequences

What are the trade-offs?

## Alternatives Considered

What else did we consider?
```

---

## Common Patterns

### Configuration Pattern

```python
# ✅ CORRECT - Use Settings
from kira.config.settings import load_settings

def my_function():
    settings = load_settings()
    return settings.some_parameter
```

### HostAPI Pattern

```python
# ✅ CORRECT - All writes through HostAPI
from kira.core.host import create_host_api

host_api = create_host_api(vault_path)
entity = host_api.create_entity("task", data)

# ❌ INCORRECT - Direct file writes
with open(vault_path / "tasks" / "task.md", "w") as f:
    f.write(content)  # Bypasses validation!
```

### Event Bus Pattern

```python
# ✅ CORRECT - Publish events
event_bus.publish(Event(
    name="task.created",
    payload={"task_id": task.id}
))

# Subscribe to events
def handle_task_created(event: Event):
    task_id = event.payload["task_id"]
    # ... handle event

event_bus.subscribe("task.created", handle_task_created)
```

---

## Questions?

- **Architecture questions:** Create issue with `question` label
- **Bug reports:** Create issue with detailed reproduction steps
- **Feature requests:** Discuss in issue first before implementing

---

**Thank you for contributing to Kira!** 🚀

Your adherence to these standards ensures Kira remains maintainable, testable, and production-ready.

---

**Document Version:** 1.0
**Last Updated:** 2025-10-09
**Maintainer:** Kira Development Team
