# ADR-004: Standardized Event Envelope

## Status

**Accepted** (Phase 2, Point 9)

## Context

Kira has multiple event sources (Telegram, GCal, CLI) and consumers. Without a standard format:

- **Incompatibility**: Each source uses different structure
- **Missing metadata**: No correlation IDs, timestamps
- **Fragile integrations**: Changes break multiple consumers
- **Difficult debugging**: Can't trace event flow

**Requirement**: Unified event structure for all sources/consumers.

## Decision

### Standard Envelope

```python
{
    "event_id": str,      # Idempotency key (ADR-003)
    "event_ts": str,      # ISO-8601 UTC timestamp
    "seq": int | None,    # Sequence number (optional)
    "source": str,        # "telegram", "gcal", "cli", etc.
    "type": str,          # "task.created", "task.updated", etc.
    "payload": dict,      # Event-specific data
}
```

**Properties:**
- `event_id`: For deduplication (see ADR-003)
- `event_ts`: When event occurred (UTC)
- `seq`: Ordering hint within same timestamp
- `source`: Origin system
- `type`: Event semantic type
- `payload`: Actual event data

### Delivery Semantics

- **At-least-once**: Events may be delivered multiple times
- **Best-effort ordering**: Use `event_ts` + `seq` for ordering
- **Idempotent consumers**: Must handle duplicates (via `event_id`)

### Example

```python
# Telegram message received
{
    "event_id": "a1b2c3...",
    "event_ts": "2025-10-08T14:30:00+00:00",
    "seq": None,
    "source": "telegram",
    "type": "message.received",
    "payload": {
        "message_id": 12345,
        "text": "Buy milk",
        "from": "user-123"
    }
}
```

## Consequences

### Positive

- **Interoperability**: All systems speak same language
- **Traceable**: Correlation ID for debugging
- **Testable**: Easy to mock/inject events
- **Evolvable**: Payload can change without breaking envelope

### Negative

- **Overhead**: Extra metadata on every event
- **Migration**: Existing code needs updating
- **Complexity**: Envelope wrapping/unwrapping

### Design Principles

1. **Metadata in envelope**: Timestamps, IDs, source
2. **Data in payload**: Event-specific information
3. **Immutable envelope**: Once created, never modified
4. **Versioned payloads**: Payload structure can evolve

## Implementation

### Event Creation

```python
def create_event_envelope(
    source: str,
    event_type: str,
    payload: dict,
    external_id: str | None = None,
) -> dict:
    """Create standardized event envelope."""
    # Generate idempotency key
    event_id = generate_event_id(source, external_id, payload)
    
    return {
        "event_id": event_id,
        "event_ts": datetime.now(timezone.utc).isoformat(),
        "seq": None,
        "source": source,
        "type": event_type,
        "payload": payload,
    }
```

### Event Validation

```python
def validate_event_envelope(event: dict) -> bool:
    """Validate event follows standard envelope."""
    required_fields = ["event_id", "event_ts", "source", "type", "payload"]
    return all(field in event for field in required_fields)
```

## Verification

### DoD Check

```python
def test_mixed_producers_interoperate():
    """Test DoD: Mixed producers interoperate."""
    # Telegram event
    telegram_event = create_event_envelope("telegram", "message", {...})
    
    # GCal event  
    gcal_event = create_event_envelope("gcal", "event.created", {...})
    
    # Both follow same structure
    assert validate_event_envelope(telegram_event)
    assert validate_event_envelope(gcal_event)
    
    # Consumer can process both
    process_event(telegram_event)  # Works
    process_event(gcal_event)      # Works
```

### Tests

- `tests/unit/test_event_envelope.py`: Envelope validation
- `tests/integration/`: Mixed source scenarios

## References

- Implementation: `src/kira/core/event_envelope.py`
- Related: ADR-003 (Idempotency), ADR-005 (Timezone)
