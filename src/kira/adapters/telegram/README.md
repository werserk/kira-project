# Telegram Adapter

**Primary UX interface for Kira via Telegram Bot API.**

The Telegram adapter provides conversational interaction with Kira through Telegram, including message capture, inline confirmations, and scheduled briefings.

---

## Features

- ✅ **Long Polling** - Continuous updates from Telegram API
- ✅ **Message Normalization** - Convert Telegram format to Kira events
- ✅ **Inline Confirmations** - Button-based user confirmation workflows
- ✅ **Daily/Weekly Briefings** - Scheduled summaries sent to chats
- ✅ **File Handling** - Photos and documents support
- ✅ **CSRF Protection** - Signed callback data for security
- ✅ **Idempotency** - Duplicate message detection
- ✅ **Whitelist** - Chat/user access control
- ✅ **Structured Logging** - JSONL logs with trace IDs

---

## Quick Start

### Installation

```bash
# Install dependencies
poetry install

# Set environment variables
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_ALLOWED_CHAT_IDS="123456789,987654321"
```

### Basic Usage

```python
from kira.adapters.telegram import create_telegram_adapter
from kira.core.events import create_event_bus

# Create event bus
event_bus = create_event_bus()

# Create adapter
adapter = create_telegram_adapter(
    bot_token="YOUR_BOT_TOKEN",
    event_bus=event_bus,
    allowed_chat_ids=[123456789],
    log_path="logs/adapters/telegram.jsonl"
)

# Subscribe to events
event_bus.subscribe("message.received", handle_message)

# Start polling (blocks until stopped)
adapter.start_polling()
```

---

## Configuration

### TelegramAdapterConfig

```python
@dataclass
class TelegramAdapterConfig:
    bot_token: str                          # Telegram Bot API token (required)
    allowed_chat_ids: list[int] = []       # Whitelist of chat IDs
    allowed_user_ids: list[int] = []       # Whitelist of user IDs
    polling_timeout: int = 30               # Long polling timeout (seconds)
    polling_interval: float = 1.0           # Delay between polls (seconds)
    max_retries: int = 3                    # Max retry attempts on errors
    retry_delay: float = 2.0                # Delay between retries (seconds)
    log_path: Path | None = None            # Path for JSONL logs
    temp_dir: Path | None = None            # Directory for file downloads
    csrf_secret: str = ...                  # Secret for CSRF tokens (auto-generated)
    daily_briefing_time: str = "09:00"      # Daily briefing time (HH:MM)
    weekly_briefing_day: int = 1            # Weekly briefing day (0=Mon, 6=Sun)
    weekly_briefing_time: str = "09:00"     # Weekly briefing time (HH:MM)
```

### Example Configuration

```python
config = TelegramAdapterConfig(
    bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    allowed_chat_ids=[int(x) for x in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS").split(",")],
    polling_timeout=30,
    log_path=Path("logs/adapters/telegram.jsonl"),
    daily_briefing_time="08:00",
    weekly_briefing_day=1,  # Monday
    weekly_briefing_time="09:00"
)

adapter = TelegramAdapter(config, event_bus=event_bus)
```

---

## Events Published

### 1. `message.received`

Published when a text message is received.

**Payload:**
```json
{
  "message": "Create task: Review Q4 report",
  "source": "telegram",
  "chat_id": 123456789,
  "user_id": 987654321,
  "message_id": 42,
  "timestamp": "2025-10-08T13:42:00Z",
  "trace_id": "a1b2c3d4-..."
}
```

**Subscribers:** Inbox plugin, AI agent

---

### 2. `file.dropped`

Published when a file or photo is received.

**Payload:**
```json
{
  "file_id": "BQACAgIAA...",
  "mime_type": "application/pdf",
  "size": 1024000,
  "source": "telegram",
  "chat_id": 123456789,
  "user_id": 987654321,
  "message_id": 43,
  "timestamp": "2025-10-08T13:45:00Z",
  "trace_id": "e5f6g7h8-..."
}
```

**Subscribers:** Filesystem importer, OCR plugin

---

### 3. `telegram.callback`

Published when inline button is clicked (legacy format).

**Payload:**
```json
{
  "callback_id": "callback_xyz",
  "data": "confirm_yes",
  "chat_id": 123456789,
  "trace_id": "i9j0k1l2-...",
  "timestamp": "2025-10-08T13:50:00Z"
}
```

**Note:** Modern confirmations use command handlers instead.

---

## Confirmation Workflow

The adapter supports interactive confirmations via inline buttons:

### Request Confirmation

```python
# From plugin or agent
adapter.request_confirmation(
    chat_id=123456789,
    message="Is this a task?\n\n'Review Q4 report by Friday'",
    options=[
        {"text": "✅ Yes, create task", "callback_data": "yes"},
        {"text": "❌ No, it's a note", "callback_data": "no"},
        {"text": "🔄 Ask me again", "callback_data": "later"}
    ],
    command="inbox.confirm_task",
    context={
        "entity_id": "task-20251008-1342",
        "title": "Review Q4 report",
        "due": "2025-10-11T17:00:00Z"
    }
)
```

### Register Handler

```python
def handle_task_confirmation(context: dict) -> None:
    choice = context["choice"]
    entity_id = context["entity_id"]

    if choice == "yes":
        # Create task in vault
        host_api.create_entity("task", {...})
    elif choice == "no":
        # Create note instead
        host_api.create_entity("note", {...})
    elif choice == "later":
        # Re-queue for later
        pass

# Register handler
adapter.register_command_handler("inbox.confirm_task", handle_task_confirmation)
```

### Security: CSRF Protection

All callback buttons are signed with HMAC:

```
Callback Data Format: {request_id}:{choice}:{signature}
Example: req-abc123:yes:d4e5f6g7h8
```

The adapter automatically:
1. Signs callback data when creating buttons
2. Verifies signature when button is clicked
3. Rejects tampered callbacks

**Expiration:** Confirmations expire after 1 hour.

---

## Briefings

The adapter can send scheduled daily and weekly briefings.

### Setup Briefing Generator

```python
from kira.adapters.telegram import BriefingScheduler

# Create briefing scheduler with Vault access
briefing = BriefingScheduler(host_api=host_api)

# Set generator function
adapter.set_briefing_generator(lambda t:
    briefing.generate_daily_briefing() if t == "daily"
    else briefing.generate_weekly_briefing()
)
```

### Manual Briefing

```python
# Send daily briefing now
adapter.send_daily_briefing(
    chat_id=123456789,
    briefing_content="📅 *Today's Summary*\n\n..."
)

# Send weekly briefing
adapter.send_weekly_briefing(
    chat_id=123456789
)
```

### Automatic Scheduling

When a scheduler is provided, briefings are sent automatically:

```python
from kira.core.scheduler import create_scheduler

scheduler = create_scheduler()

adapter = create_telegram_adapter(
    bot_token="...",
    event_bus=event_bus,
    scheduler=scheduler,  # Enables auto-briefings
    daily_briefing_time="08:00",
    weekly_briefing_day=1,  # Monday
    weekly_briefing_time="09:00"
)
```

**Briefing Content Example:**

```markdown
📅 *Daily Briefing*

*🌅 Good Morning!*

Here's what's on your agenda today:

📋 *Tasks Due Today (3):*
  • Review Q4 report
  • Team standup at 10am
  • Draft proposal

📅 *Events Today (2):*
  • 10:00 Team Standup (Zoom)
  • 14:00 Client call

✨ *Have a productive day!*
```

---

## Idempotency

The adapter tracks processed messages to prevent duplicates:

```python
# Idempotency key format
key = f"{chat_id}:{message_id}"

# Automatic deduplication
if key in self._processed_updates:
    return  # Skip duplicate

self._processed_updates.add(key)
```

**Storage:** In-memory set with LRU cleanup (keeps last 10,000).

---

## Logging

All operations are logged in structured JSONL format:

```json
{
  "timestamp": "2025-10-08T13:42:00Z",
  "component": "adapter",
  "adapter": "telegram",
  "event_type": "message_received",
  "trace_id": "a1b2c3d4",
  "chat_id": 123456789,
  "message_id": 42,
  "outcome": "success"
}
```

### Log Events

- `polling_started` - Polling loop started
- `polling_stopped` - Polling loop stopped
- `message_received` - Message processed successfully
- `message_duplicate` - Duplicate message skipped
- `message_rejected` - Message from non-whitelisted user
- `message_published` - Event published to bus
- `file_dropped` - File received and published
- `confirmation_requested` - Confirmation buttons sent
- `callback_received` - Button clicked
- `callback_command_executed` - Handler executed successfully
- `callback_csrf_failed` - CSRF verification failed
- `briefing_sent` - Briefing delivered successfully
- `polling_error` - Error during polling

---

## Error Handling

### Automatic Retry

API errors trigger exponential backoff:

```python
for attempt in range(max_retries):
    try:
        return self._api_request(method, params)
    except APIError as e:
        if attempt < max_retries - 1:
            time.sleep(retry_delay * (2 ** attempt))
        else:
            raise
```

### Graceful Degradation

Non-critical errors are logged but don't stop polling:

```python
try:
    self._process_update(update)
except Exception as exc:
    self._log_event("update_processing_failed", {
        "error": str(exc),
        "trace_id": trace_id
    })
    # Continue polling
```

---

## Testing

### Unit Tests

```python
def test_message_normalization():
    adapter = create_telegram_adapter("test_token")

    raw_message = {
        "message_id": 42,
        "chat": {"id": 123456},
        "from": {"id": 987654},
        "text": "Hello",
        "date": 1696777200
    }

    message = adapter._parse_message(raw_message)

    assert message.chat_id == 123456
    assert message.text == "Hello"

def test_idempotency():
    adapter = create_telegram_adapter("test_token")

    message = TelegramMessage(
        message_id=42,
        chat_id=123456,
        user_id=987654,
        text="test"
    )

    key = message.get_idempotency_key()
    assert key == "123456:42"
```

### Integration Tests

```python
def test_confirmation_workflow():
    event_bus = create_event_bus()
    adapter = create_telegram_adapter("test", event_bus=event_bus)

    executed = []

    def handler(ctx):
        executed.append(ctx["choice"])

    adapter.register_command_handler("test.confirm", handler)

    request_id = adapter.request_confirmation(
        chat_id=123456,
        message="Confirm?",
        options=[{"text": "Yes", "callback_data": "yes"}],
        command="test.confirm"
    )

    # Simulate button click
    adapter._handle_callback_query({
        "id": "cb_123",
        "data": f"{request_id}:yes:...",
        "message": {"chat": {"id": 123456}},
        "from": {"id": 987654}
    }, "trace_123")

    assert executed == ["yes"]
```

---

## Best Practices

### ✅ DO

1. **Always whitelist chats/users** in production
2. **Use confirmation workflows** for destructive actions
3. **Set up briefings** to keep users engaged
4. **Handle files asynchronously** (publish event, process later)
5. **Log with trace_id** for debugging
6. **Test CSRF protection** in security audits

### ❌ DON'T

1. **Don't expose bot token** in logs or commits
2. **Don't process messages without idempotency check**
3. **Don't trust callback data** without verification
4. **Don't block polling loop** with long operations
5. **Don't store sensitive data** in confirmation context

---

## Architecture

```
Telegram API
     ↓
Long Polling (getUpdates)
     ↓
Parse & Validate
     ↓
Idempotency Check
     ↓
Whitelist Check
     ↓
┌────────────────┬─────────────────┐
│  Text Message  │  File/Photo     │  Callback Query
│                │                 │
↓                ↓                 ↓
message.received  file.dropped     Command Handler
     ↓                ↓                   ↓
Event Bus        Event Bus         Plugin Logic
     ↓                ↓                   ↓
Plugins          Plugins           Vault Update
```

---

## Troubleshooting

### Polling Not Working

**Check:**
1. Bot token is valid
2. Network connectivity
3. Polling timeout not too short

**Debug:**
```python
adapter.config.polling_timeout = 10
adapter.start_polling()  # Check logs for errors
```

### Messages Not Received

**Check:**
1. Chat ID is whitelisted
2. Idempotency store not full
3. Event bus has subscribers

**Debug:**
```bash
# Check logs
tail -f logs/adapters/telegram.jsonl | grep message_received

# Verify whitelist
echo $TELEGRAM_ALLOWED_CHAT_IDS
```

### Confirmations Not Working

**Check:**
1. Command handler registered
2. CSRF secret consistent across restarts
3. Confirmation not expired (1 hour TTL)

**Debug:**
```python
adapter._pending_confirmations  # Check pending requests
```

---

## References

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- **ADR-011:** Telegram Adapter Specification
- **ADR-003:** Event Idempotency
- **ADR-005:** Structured Logging

---

## Example: Full Integration

```python
from kira.adapters.telegram import create_telegram_adapter, BriefingScheduler
from kira.core.events import create_event_bus
from kira.core.host_api import create_host_api
from kira.core.scheduler import create_scheduler

# Initialize components
vault_path = Path("vault")
event_bus = create_event_bus()
host_api = create_host_api(vault_path, event_bus=event_bus)
scheduler = create_scheduler()

# Create briefing generator
briefing = BriefingScheduler(host_api=host_api)

# Create adapter
adapter = create_telegram_adapter(
    bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    event_bus=event_bus,
    scheduler=scheduler,
    allowed_chat_ids=[int(os.getenv("TELEGRAM_CHAT_ID"))],
    log_path=Path("logs/adapters/telegram.jsonl"),
    daily_briefing_time="08:00",
    weekly_briefing_day=1,
    weekly_briefing_time="09:00"
)

# Setup briefings
adapter.set_briefing_generator(lambda t:
    briefing.generate_daily_briefing() if t == "daily"
    else briefing.generate_weekly_briefing()
)

# Subscribe to events
def handle_message(event):
    message = event.payload["message"]
    chat_id = event.payload["chat_id"]

    # Process with AI agent
    response = agent.process(message)

    # Send response
    adapter.send_message(chat_id, response)

event_bus.subscribe("message.received", handle_message)

# Start adapter
adapter.start_polling()  # Blocks until Ctrl+C
```

---

**Status:** ✅ Production Ready
**Version:** 1.0.0
**Last Updated:** 2025-10-08
