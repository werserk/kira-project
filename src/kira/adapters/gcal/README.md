# Google Calendar Adapter

**Two-way synchronization between Kira Vault and Google Calendar.**

The GCal adapter enables seamless integration with Google Calendar, supporting event import, timeboxing, and conflict resolution.

---

## Features

- ✅ **Pull Events** - Import events from Google Calendar
- ✅ **Push Entities** - Sync Vault tasks/events to GCal
- ✅ **Conflict Resolution** - Last-writer-wins strategy
- ✅ **Timebox Creation** - Automatic time blocking for tasks
- ✅ **Event Mapping** - Track sync state between systems
- ✅ **Rate Limiting** - Respect Google API quotas
- ✅ **Structured Logging** - JSONL logs with trace IDs

---

## Quick Start

### Prerequisites

1. **Google Cloud Project** with Calendar API enabled
2. **OAuth 2.0 Credentials** (download `credentials.json`)
3. **Python packages:** `google-api-python-client`, `google-auth`

### Installation

```bash
# Install dependencies
poetry add google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Place credentials.json in project root
cp ~/Downloads/credentials.json ./credentials.json
```

### Basic Usage

```python
from kira.adapters.gcal import create_gcal_adapter
from kira.core.events import create_event_bus
from pathlib import Path

# Create event bus
event_bus = create_event_bus()

# Create adapter
adapter = create_gcal_adapter(
    credentials_path=Path("credentials.json"),
    event_bus=event_bus,
    log_path=Path("logs/adapters/gcal.jsonl"),
    calendar_id="primary",
    sync_days_future=30
)

# Pull events from Google Calendar
result = adapter.pull()
print(f"Pulled {result.pulled} events")

# Push Vault entities to Google Calendar
entities = [...]  # Vault entities
result = adapter.push(entities)
print(f"Pushed {result.pushed} entities")
```

---

## Configuration

### GCalAdapterConfig

```python
@dataclass
class GCalAdapterConfig:
    credentials_path: Path | None = None    # Path to credentials.json
    token_path: Path | None = None          # Path to token.json (auto-generated)
    calendar_id: str = "primary"            # Calendar ID to sync
    sync_days_past: int = 7                 # Days to sync in the past
    sync_days_future: int = 30              # Days to sync in the future
    rate_limit_delay: float = 0.1           # Delay between API calls (seconds)
    max_retries: int = 3                    # Max retry attempts
    retry_delay: float = 2.0                # Delay between retries (seconds)
    log_path: Path | None = None            # Path for JSONL logs
```

### Example Configuration

```python
config = GCalAdapterConfig(
    credentials_path=Path("credentials.json"),
    token_path=Path(".gcal_token.json"),
    calendar_id="primary",
    sync_days_past=7,
    sync_days_future=30,
    rate_limit_delay=0.1,
    log_path=Path("logs/adapters/gcal.jsonl")
)

adapter = GCalAdapter(config, event_bus=event_bus)
```

---

## Operations

### 1. Pull Events (Import from GCal)

Pull events from Google Calendar and publish to event bus:

```python
result = adapter.pull(
    calendar_id="primary",  # Optional: override config
    days=30                 # Optional: override config
)

print(f"Pulled: {result.pulled}")
print(f"Errors: {result.errors}")
print(f"Duration: {result.duration_ms}ms")
```

**What happens:**
1. Fetch events from GCal API
2. For each event:
   - Normalize to Kira format
   - Publish `event.received` to event bus
   - Respect rate limits (delay between events)
3. Return statistics

**Event Published:**

```json
{
  "event_type": "event.received",
  "source": "gcal",
  "gcal_id": "abc123xyz",
  "summary": "Team Standup",
  "start": "2025-10-08T10:00:00Z",
  "end": "2025-10-08T10:30:00Z",
  "description": "Daily standup meeting",
  "location": "Zoom",
  "attendees": ["user@example.com"],
  "all_day": false,
  "trace_id": "a1b2c3d4..."
}
```

---

### 2. Push Entities (Export to GCal)

Push Vault entities to Google Calendar:

```python
# Get entities from Vault
from kira.core.host_api import create_host_api

host_api = create_host_api(Path("vault"))
entities = list(host_api.list_entities("event", limit=50))

# Push to GCal
result = adapter.push(
    entities,
    calendar_id="primary",
    dry_run=False  # Set to True to preview without pushing
)

print(f"Pushed: {result.pushed}")
print(f"Skipped: {result.skipped}")
print(f"Errors: {result.errors}")
```

**What happens:**
1. For each entity:
   - Convert to GCal event format
   - Check if needs push (based on last sync)
   - Create or update in GCal
   - Respect rate limits
2. Return statistics

**Entity Requirements:**
- Must have `start` or `due` field (datetime)
- Optional: `end`, `time_hint`, `location`, `attendees`

---

### 3. Reconcile (Conflict Resolution)

Detect and resolve conflicts between Vault and GCal:

```python
entities = list(host_api.list_entities("event"))

result = adapter.reconcile(entities)

print(f"Conflicts: {result.conflicts}")
print(f"Pulled (GCal newer): {result.pulled}")
print(f"Pushed (Vault newer): {result.pushed}")
```

**Conflict Resolution Strategy:**

Last-writer-wins based on `updated` timestamps:

```python
if vault_updated > gcal_updated:
    # Vault is newer → push to GCal
    adapter._push_event(calendar_id, gcal_event)
else:
    # GCal is newer → pull to Vault
    adapter._publish_event_received(gcal_event, trace_id)
```

**Conflict Detection:**
- Events with same `gcal_id` in both systems
- `updated` timestamps differ by more than 60 seconds

---

### 4. Create Timebox

Create time-blocked calendar event for task:

```python
# Get task from Vault
task = host_api.read_entity("task-20251008-1342")

# Create timebox in GCal
gcal_id = adapter.create_timebox(
    task,
    calendar_id="primary"
)

print(f"Timebox created: {gcal_id}")
```

**Timebox Event:**
- Title: `🔲 {task.title}`
- Description: `[TIMEBOX] ...`
- Duration: Based on `time_hint` (default: 1 hour)
- Start: Based on `due` or `start` field

**Use Case:** Block time on calendar when starting a task.

---

## Event Mapping

The adapter tracks sync state between Vault and GCal:

```python
@dataclass
class EventMapping:
    vault_id: str                # Vault entity ID
    gcal_id: str                 # GCal event ID
    vault_updated: datetime      # Last update in Vault
    gcal_updated: datetime       # Last update in GCal
    last_synced: datetime        # Last successful sync
    sync_direction: str          # "vault_to_gcal", "gcal_to_vault", "bidirectional"
```

**Stored in:** Entity frontmatter

```yaml
---
id: event-20251008-1000
gcal_id: abc123xyz
gcal_last_synced: 2025-10-08T10:00:00Z
---
```

---

## GCal Event Format

### Converting Vault Entity to GCal

```python
gcal_event = GCalEvent.from_vault_entity(entity)

# Result:
{
    "id": "vault-task-20251008-1342",
    "summary": "Review Q4 report",
    "start": "2025-10-11T14:00:00Z",
    "end": "2025-10-11T15:00:00Z",
    "description": "Need to review...\n\n[View in Vault: task-20251008-1342]",
    "location": null,
    "attendees": [],
    "all_day": false
}
```

### Vault Entity Requirements

**Minimal Event:**
```yaml
---
id: event-20251008-1000
kind: event
start: 2025-10-08T10:00:00Z
end: 2025-10-08T11:00:00Z
---
# Team Standup
```

**Minimal Task (for timebox):**
```yaml
---
id: task-20251008-1342
kind: task
due: 2025-10-11T17:00:00Z
time_hint: 2h
---
# Review Q4 report
```

---

## Rate Limiting

The adapter respects Google Calendar API quotas:

```python
# Default: 0.1s between requests (10 req/sec)
adapter.config.rate_limit_delay = 0.1

# Conservative: 0.5s (2 req/sec)
adapter.config.rate_limit_delay = 0.5
```

**Google Calendar Limits:**
- **Quota:** 1,000,000 queries/day
- **Rate:** 10 queries/second per user

**Automatic Retry:**
- Rate limit errors → exponential backoff
- Transient errors → retry up to 3 times

---

## Logging

All operations are logged in structured JSONL format:

```json
{
  "timestamp": "2025-10-08T10:00:00Z",
  "component": "adapter",
  "adapter": "gcal",
  "event_type": "gcal_pull_started",
  "trace_id": "a1b2c3d4",
  "calendar_id": "primary",
  "days": 30
}
```

### Log Events

- `gcal_pull_started` / `gcal_pull_completed` - Pull operation
- `gcal_push_started` / `gcal_push_completed` - Push operation
- `gcal_reconcile_started` / `gcal_reconcile_completed` - Reconciliation
- `gcal_conflict_resolved` - Conflict detected and resolved
- `timebox_created` - Timebox event created
- `gcal_pull_failed` / `gcal_push_failed` - Errors

---

## Error Handling

### Retry Logic

```python
for attempt in range(max_retries):
    try:
        return self._api_request(...)
    except RateLimitError:
        delay = retry_delay * (2 ** attempt)
        time.sleep(delay)
    except TransientError:
        time.sleep(retry_delay)
    else:
        break
```

### Error Collection

Errors are collected per operation:

```python
result = adapter.pull()

if result.errors > 0:
    for error in result.error_messages:
        print(f"Error: {error}")
```

---

## Testing

### Unit Tests

```python
def test_gcal_event_creation():
    from kira.adapters.gcal import GCalEvent
    from datetime import datetime, UTC

    event = GCalEvent(
        id="test-123",
        summary="Test Event",
        start=datetime(2025, 10, 8, 10, 0, tzinfo=UTC),
        end=datetime(2025, 10, 8, 11, 0, tzinfo=UTC),
        all_day=False
    )

    event_dict = event.to_dict()

    assert event_dict["summary"] == "Test Event"
    assert "dateTime" in event_dict["start"]

def test_entity_to_gcal_conversion():
    from kira.core.entities import Entity

    entity = Entity(
        id="event-20251008-1000",
        kind="event",
        metadata={
            "start": "2025-10-08T10:00:00Z",
            "end": "2025-10-08T11:00:00Z",
            "location": "Zoom"
        },
        content="# Team Standup"
    )

    gcal_event = GCalEvent.from_vault_entity(entity)

    assert gcal_event.location == "Zoom"
```

### Integration Tests

```python
def test_pull_and_push_cycle(mock_gcal_api):
    event_bus = create_event_bus()
    adapter = create_gcal_adapter(
        credentials_path=None,  # Mock
        event_bus=event_bus
    )

    # Mock API responses
    mock_gcal_api.events = [...]

    # Pull
    result = adapter.pull()
    assert result.pulled > 0

    # Push
    entities = [...]
    result = adapter.push(entities)
    assert result.pushed > 0
```

---

## Best Practices

### ✅ DO

1. **Enable API** in Google Cloud Console before use
2. **Store credentials securely** (not in git)
3. **Use rate limiting** to avoid quota exhaustion
4. **Implement conflict resolution** for bidirectional sync
5. **Log with trace_id** for debugging sync issues
6. **Test with dry_run** before pushing to production calendar

### ❌ DON'T

1. **Don't commit `credentials.json` or `token.json`**
2. **Don't sync all history** (use reasonable `sync_days_*`)
3. **Don't push without `gcal_id` tracking** (causes duplicates)
4. **Don't ignore rate limits** (will trigger API blocks)
5. **Don't sync sensitive data** without encryption

---

## OAuth Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "Kira Integration"
3. Enable **Google Calendar API**

### 2. Create OAuth Credentials

1. Navigate to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Desktop app**
4. Download credentials as `credentials.json`

### 3. First-Time Authorization

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json', SCOPES
)

creds = flow.run_local_server(port=0)

# Save token for future use
with open('token.json', 'w') as token:
    token.write(creds.to_json())
```

**Browser will open** for authorization. After approval, token is saved.

### 4. Subsequent Use

Token is refreshed automatically by the adapter.

---

## Conflict Resolution Example

### Scenario

1. **Vault:** Event updated at 10:00
2. **GCal:** Same event updated at 10:05
3. **Reconcile called at 10:10**

### Resolution

```python
result = adapter.reconcile(vault_entities)

# Log output:
{
  "event_type": "gcal_conflict_resolved",
  "entity_id": "event-20251008-1000",
  "gcal_id": "abc123xyz",
  "resolution": "gcal_newer",  # GCal wins
  "vault_updated": "2025-10-08T10:00:00Z",
  "gcal_updated": "2025-10-08T10:05:00Z"
}

# Result:
# - GCal event is pulled to Vault
# - Vault entity is updated with GCal data
# - result.pulled == 1
```

---

## Timeboxing Workflow

### Use Case

User starts working on a task → automatically block time on calendar.

### Implementation

```python
from kira.core.events import create_event_bus

event_bus = create_event_bus()

# Subscribe to task state changes
def handle_task_started(event):
    if event.payload.get("new_status") == "doing":
        task_id = event.payload["entity_id"]

        # Get task
        task = host_api.read_entity(task_id)

        # Create timebox
        adapter.create_timebox(task)

event_bus.subscribe("entity.updated", handle_task_started)
```

### Result

```
Calendar:
┌─────────────────────────────────┐
│ 14:00 - 16:00                   │
│ 🔲 Review Q4 report             │
│ [TIMEBOX]                       │
└─────────────────────────────────┘
```

---

## References

- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- **ADR-012:** Google Calendar Sync Protocol
- **ADR-003:** Event Idempotency
- **ADR-005:** Structured Logging

---

## Troubleshooting

### OAuth Errors

**Problem:** `RefreshError: invalid_grant`

**Solution:**
1. Delete `token.json`
2. Re-authorize (browser will open)
3. Accept permissions

### Rate Limit Exceeded

**Problem:** `429 Rate Limit Exceeded`

**Solution:**
```python
adapter.config.rate_limit_delay = 0.5  # Increase delay
adapter.config.max_retries = 5         # More retries
```

### Duplicate Events

**Problem:** Same event appears multiple times in GCal

**Solution:**
- Ensure entities have `gcal_id` stored after first push
- Use `reconcile()` to clean up duplicates

---

**Status:** ✅ Production Ready
**Version:** 1.0.0
**Last Updated:** 2025-10-08
