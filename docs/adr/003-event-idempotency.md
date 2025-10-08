# ADR-003: Event Idempotency Keys

## Status

**Accepted** (Phase 2, Point 7)

## Context

Kira processes events from multiple sources (Telegram, Google Calendar, CLI). Events can be:

- **Duplicated**: Network retries, webhook replays
- **Reordered**: Out-of-order delivery
- **Replayed**: Recovery scenarios, debugging

Without idempotency:
- Duplicate tasks created
- Actions executed twice
- State corruption

**Requirement**: Process each logical event exactly once, even with at-least-once delivery.

## Decision

### Idempotency Key Generation

```python
event_id = sha256(
    source,          # "telegram", "gcal", "cli"
    external_id,     # External unique identifier
    normalized_payload  # Normalized event data
)
```

**Properties:**
- **Deterministic**: Same event → same ID
- **Unique**: Different events → different IDs
- **Stable**: Doesn't change on replay

### Dedupe Store

Track seen events in SQLite:

```sql
CREATE TABLE seen_events (
    event_id TEXT PRIMARY KEY,
    first_seen_ts TEXT NOT NULL,
    last_seen_ts TEXT NOT NULL
);
```

**Operations:**
- `is_duplicate(event_id)`: Check if seen
- `mark_seen(event_id)`: Record as processed
- `cleanup(ttl_days)`: Remove old events

### Processing Flow

```python
event_id = generate_event_id(source, external_id, payload)

if dedupe_store.is_duplicate(event_id):
    logger.info("Duplicate event, skipping", event_id=event_id)
    return  # No-op

# Process event
result = process_event(payload)

# Mark as seen
dedupe_store.mark_seen(event_id)
```

## Consequences

### Positive

- **Idempotency**: Duplicate events are no-ops
- **Reliability**: Safe to retry on failures
- **Debugging**: Can replay events without side effects
- **Auditability**: Track when events first/last seen

### Negative

- **Storage**: Dedupe store grows over time (mitigated by TTL)
- **Dependency**: Requires SQLite database
- **Complexity**: Extra step in event processing

### TTL Strategy

- **Default TTL**: 30 days
- **Cleanup**: Scheduled job removes old entries
- **Trade-off**: Memory vs. duplicate window

## Implementation

### Event ID Generation

```python
def generate_event_id(source: str, external_id: str, payload: dict) -> str:
    """Generate deterministic event ID."""
    # Normalize payload for stability
    normalized = json.dumps(payload, sort_keys=True)
    
    # Hash components
    data = f"{source}:{external_id}:{normalized}"
    return hashlib.sha256(data.encode()).hexdigest()
```

### Dedupe Store

```python
class EventDedupeStore:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self._init_schema()
    
    def is_duplicate(self, event_id: str) -> bool:
        """Check if event already seen."""
        cursor = self.conn.execute(
            "SELECT 1 FROM seen_events WHERE event_id = ?",
            (event_id,)
        )
        return cursor.fetchone() is not None
    
    def mark_seen(self, event_id: str):
        """Mark event as seen."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO seen_events (event_id, first_seen_ts, last_seen_ts)
            VALUES (?, ?, ?)
            ON CONFLICT (event_id) 
            DO UPDATE SET last_seen_ts = ?
        """, (event_id, now, now, now))
        self.conn.commit()
```

## Verification

### DoD Check

```python
def test_duplicate_event_is_noop():
    """Test DoD: Re-publishing same event is no-op."""
    event_id = generate_event_id("test", "123", {"data": "test"})
    
    # First time: processed
    assert not dedupe_store.is_duplicate(event_id)
    dedupe_store.mark_seen(event_id)
    
    # Second time: skipped
    assert dedupe_store.is_duplicate(event_id)
```

### Tests

- `tests/unit/test_idempotency.py`: Dedup logic
- `tests/integration/test_telegram_vault_integration.py`: E2E idempotency

## References

- Implementation: `src/kira/core/idempotency.py`
- Usage: All adapters (Telegram, GCal, CLI)
- Related: ADR-004 (Event Envelope), ADR-006 (GCal Sync)
