# Kira Adapters

**External system integrations for the Kira agent.**

Adapters provide bidirectional communication between Kira's core and external services. Each adapter follows a consistent pattern: normalize inputs, publish events to the event bus, and handle responses.

---

## Overview

Adapters are the ingress/egress layer for Kira. They:

- **Normalize** data from external sources into Kira's event format
- **Publish** events to the event bus for plugin consumption
- **Handle** responses and send data back to external systems
- **Maintain** idempotency and structured logging
- **Enforce** rate limits and error handling

```
External Service  →  Adapter  →  Event Bus  →  Core/Plugins
                  ←           ←             ←
```

---

## Available Adapters

### 📱 Telegram Adapter (`telegram/`)

Primary UX interface via Telegram Bot API.

**Features:**
- Long polling for updates
- Inline button confirmations
- Daily/weekly briefings
- File/photo handling
- CSRF protection
- Idempotency tracking

**Use Cases:**
- Quick task capture via chat
- Confirmation workflows
- Scheduled briefings
- Mobile-first interaction

📖 [Read more](./telegram/README.md)

---

### 📅 Google Calendar Adapter (`gcal/`)

Two-way sync with Google Calendar.

**Features:**
- Pull events from GCal
- Push Vault entities to GCal
- Conflict resolution (last-writer-wins)
- Timebox creation for tasks
- Event mapping and tracking

**Use Cases:**
- Calendar synchronization
- Timeboxing workflows
- External calendar integration

📖 [Read more](./gcal/README.md)

---

### 🤖 LLM Adapters (`llm/`)

Multi-provider LLM integration with routing and fallback.

**Supported Providers:**
- **Anthropic** (Claude) - Primary for planning
- **OpenAI** (GPT) - Fallback and structuring
- **OpenRouter** - Multi-model access
- **Ollama** - Local/offline fallback

**Features:**
- Provider routing by task type
- Automatic retry with exponential backoff
- Rate limit handling
- Local fallback (Ollama)
- Tool/function calling support

**Use Cases:**
- AI agent planning and reasoning
- JSON structuring
- Conversational interfaces
- Offline operation

📖 [Read more](./llm/README.md)

---

### 📁 Filesystem Adapter (`filesystem/`)

Watch directories for file changes and import to Vault.

**Features:**
- Directory watching
- File normalization
- Auto-import with schema validation
- Event emission on file drop

**Use Cases:**
- Auto-import markdown files
- Integration with file managers
- Dropbox/sync folder monitoring

*(Under development)*

---

## Architecture Patterns

### 1. Event-Driven Design

All adapters publish to the event bus instead of directly calling core functions:

```python
# ✅ Good: Publish event
event_bus.publish("message.received", {
    "message": "Create task: Review PR",
    "source": "telegram",
    "trace_id": trace_id
})

# ❌ Bad: Direct coupling
host_api.create_entity("task", {...})
```

**Benefits:**
- Loose coupling
- Plugin extensibility
- Audit trail
- Retry/replay capability

---

### 2. Idempotency

Adapters track processed items to prevent duplicates:

```python
idempotency_key = f"{source}:{external_id}"
if idempotency_key in processed:
    return  # Skip duplicate

processed.add(idempotency_key)
```

**ADR-003:** All events are idempotent with deterministic IDs.

---

### 3. Structured Logging

Every adapter emits JSONL logs with correlation:

```json
{
  "timestamp": "2025-10-08T13:42:00Z",
  "component": "adapter",
  "adapter": "telegram",
  "event_type": "message_received",
  "trace_id": "a1b2c3",
  "chat_id": 123456,
  "outcome": "success"
}
```

**Benefits:**
- Traceability across systems
- Debugging with `trace_id`
- Analytics and monitoring

---

### 4. Configuration Pattern

All adapters use dataclass configs:

```python
@dataclass
class AdapterConfig:
    api_key: str
    base_url: str = "https://api.example.com"
    timeout: float = 30.0
    retry_count: int = 3
    log_path: Path | None = None
```

**Factory functions** for easy initialization:

```python
adapter = create_telegram_adapter(
    bot_token="YOUR_TOKEN",
    event_bus=event_bus,
    allowed_chat_ids=[123456]
)
```

---

## Creating a New Adapter

### Step 1: Define Configuration

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class MyAdapterConfig:
    api_key: str
    base_url: str = "https://api.service.com"
    timeout: float = 30.0
    log_path: Path | None = None
```

### Step 2: Implement Adapter Class

```python
class MyAdapter:
    def __init__(
        self,
        config: MyAdapterConfig,
        *,
        event_bus: EventBus | None = None,
        logger: Any = None
    ):
        self.config = config
        self.event_bus = event_bus
        self.logger = logger

    def start(self) -> None:
        """Start adapter polling/watching."""
        pass

    def stop(self) -> None:
        """Stop adapter gracefully."""
        pass

    def _publish_event(self, event_type: str, payload: dict) -> None:
        """Publish normalized event to bus."""
        if self.event_bus:
            self.event_bus.publish(event_type, payload)

    def _log_event(self, event_type: str, data: dict) -> None:
        """Emit structured log."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": "adapter",
            "adapter": "my_adapter",
            "event_type": event_type,
            **data
        }
        # Write to log file...
```

### Step 3: Add Factory Function

```python
def create_my_adapter(
    api_key: str,
    *,
    event_bus: EventBus | None = None,
    logger: Any = None,
    **config_kwargs
) -> MyAdapter:
    """Factory function to create adapter."""
    config = MyAdapterConfig(api_key=api_key, **config_kwargs)
    return MyAdapter(config, event_bus=event_bus, logger=logger)
```

### Step 4: Register Events

Document events your adapter publishes:

```yaml
events:
  - name: "my_service.item_received"
    payload:
      item_id: string
      content: string
      source: "my_service"
      trace_id: string

  - name: "my_service.status_changed"
    payload:
      item_id: string
      status: string
      trace_id: string
```

### Step 5: Add Tests

```python
def test_adapter_initialization():
    config = MyAdapterConfig(api_key="test")
    adapter = MyAdapter(config)
    assert adapter.config.api_key == "test"

def test_event_publishing():
    event_bus = create_event_bus()
    adapter = create_my_adapter("test", event_bus=event_bus)

    received = []
    event_bus.subscribe("my_service.item_received",
                       lambda e: received.append(e))

    adapter._publish_event("my_service.item_received", {
        "item_id": "123",
        "content": "test"
    })

    assert len(received) == 1
```

---

## Best Practices

### ✅ DO

1. **Always emit structured logs** with `trace_id` for correlation
2. **Handle rate limits** with exponential backoff
3. **Implement idempotency** to prevent duplicate processing
4. **Normalize data** before publishing events
5. **Use factory functions** for easier testing and configuration
6. **Document event payloads** in your README
7. **Add timeout limits** to prevent hanging operations
8. **Validate external data** before processing

### ❌ DON'T

1. **Don't call Core/HostAPI directly** - use event bus
2. **Don't store state** without persistence
3. **Don't ignore errors** - log and handle gracefully
4. **Don't hardcode credentials** - use config
5. **Don't block indefinitely** - always have timeouts
6. **Don't skip idempotency** - duplicates cause issues
7. **Don't forget CSRF protection** for webhooks/callbacks

---

## Error Handling

All adapters should handle errors gracefully:

```python
def safe_operation(self, data: dict) -> None:
    trace_id = str(uuid.uuid4())

    try:
        # Perform operation
        result = self._process_data(data)

        self._log_event("operation_success", {
            "trace_id": trace_id,
            "outcome": "success"
        })

    except RateLimitError as e:
        self._log_event("rate_limit_exceeded", {
            "trace_id": trace_id,
            "retry_after": e.retry_after,
            "outcome": "failure"
        })
        # Implement backoff...

    except Exception as e:
        self._log_event("operation_failed", {
            "trace_id": trace_id,
            "error": str(e),
            "error_type": type(e).__name__,
            "outcome": "failure"
        })
```

---

## Testing

### Unit Tests

Test adapter logic in isolation:

```python
def test_message_normalization():
    adapter = create_my_adapter("test")
    raw_message = {"text": "hello", "id": "123"}
    normalized = adapter._normalize_message(raw_message)

    assert normalized["source"] == "my_service"
    assert "trace_id" in normalized
```

### Integration Tests

Test with real event bus and mocked external API:

```python
@pytest.fixture
def mock_api(monkeypatch):
    def mock_request(*args, **kwargs):
        return {"ok": True, "data": {...}}

    monkeypatch.setattr("requests.post", mock_request)

def test_end_to_end_flow(mock_api):
    event_bus = create_event_bus()
    adapter = create_my_adapter("test", event_bus=event_bus)

    received_events = []
    event_bus.subscribe("my_service.item_received",
                       lambda e: received_events.append(e))

    adapter.process_incoming({"item": "test"})

    assert len(received_events) == 1
```

---

## Performance Considerations

### Rate Limiting

Implement delays between API calls:

```python
import time

for item in items:
    self._process_item(item)
    time.sleep(self.config.rate_limit_delay)  # e.g., 0.1s
```

### Batching

Process items in batches when possible:

```python
def process_batch(self, items: list[dict]) -> None:
    batch_size = 100
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        self._send_batch(batch)
```

### Connection Pooling

Reuse HTTP connections:

```python
import httpx

class MyAdapter:
    def __init__(self, config: MyAdapterConfig):
        self.client = httpx.Client(timeout=config.timeout)

    def __del__(self):
        self.client.close()
```

---

## Security

### Credentials

Never hardcode API keys:

```python
# ✅ Good: From config/environment
api_key = os.getenv("MY_SERVICE_API_KEY")

# ❌ Bad: Hardcoded
api_key = "sk-abc123..."
```

### Input Validation

Sanitize external data:

```python
def _validate_input(self, data: dict) -> bool:
    required = ["id", "content"]
    if not all(k in data for k in required):
        return False

    # Validate types
    if not isinstance(data["id"], str):
        return False

    return True
```

### CSRF Protection

For webhooks and callbacks:

```python
def _verify_signature(self, payload: str, signature: str) -> bool:
    expected = hmac.new(
        self.config.secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
```

---

## Monitoring

### Health Checks

Implement health check endpoints:

```python
def health_check(self) -> dict:
    return {
        "status": "healthy" if self._running else "stopped",
        "uptime_seconds": time.time() - self._start_time,
        "processed_count": self._processed_count,
        "error_count": self._error_count
    }
```

### Metrics

Track key metrics:

```python
self.metrics = {
    "messages_received": 0,
    "messages_processed": 0,
    "errors": 0,
    "avg_processing_time_ms": 0.0
}
```

---

## Contributing

When adding a new adapter:

1. Create directory: `src/kira/adapters/my_adapter/`
2. Add `adapter.py` with implementation
3. Add `README.md` with documentation
4. Add tests in `tests/integration/adapters/`
5. Update this main README
6. Add to plugin registry if needed

---

## References

- **ADR-003:** Event Idempotency and Deduplication
- **ADR-005:** Structured Logging with Trace IDs
- **ADR-011:** Telegram Adapter Specification
- **ADR-012:** Google Calendar Sync Protocol

---

*For adapter-specific documentation, see individual adapter README files.*
