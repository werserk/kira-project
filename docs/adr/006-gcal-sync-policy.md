# ADR-006: Two-Way GCal Sync Policy

## Status

**Accepted** (Phase 4, Points 14-15)

## Context

Kira syncs with Google Calendar bidirectionally:

- **Kira → GCal**: Export events to calendar
- **GCal → Kira**: Import external events

Without careful design:
- **Echo loops**: Kira→GCal→Kira→GCal→... (infinite)
- **Conflicts**: Simultaneous edits in both systems
- **Lost updates**: One system overwrites the other
- **Duplicate events**: Same event created multiple times

**Requirement**: Reliable two-way sync without echo loops or data loss.

## Decision

### Sync Contract (Embedded in Front-matter)

```yaml
---
id: event-20251008-1430-team-meeting
title: Team Meeting
x-kira:
  source: kira          # Who made last write: "kira" | "gcal"
  version: 3            # Monotonically increasing
  remote_id: gcal-abc123  # Google Calendar event ID
  last_write_ts: 2025-10-08T14:30:00+00:00  # UTC timestamp
  etag: "xyz789"        # GCal ETag for optimistic locking
---
```

**Fields:**
- `source`: Origin of last write (ownership hint)
- `version`: Increments on every change
- `remote_id`: Links to GCal event
- `last_write_ts`: When last modified (for conflict resolution)
- `etag`: GCal's optimistic lock token

### Sync Flow

```
Kira Write:
  source = "kira"
  version += 1
  last_write_ts = now()
  
GCal Import:
  source = "gcal"
  version += 1  
  last_write_ts = gcal_event.updated
  remote_id = gcal_event.id
  etag = gcal_event.etag
```

### Echo Loop Prevention

**Sync Ledger** (SQLite):

```sql
CREATE TABLE sync_ledger (
    remote_id TEXT PRIMARY KEY,
    kira_uid TEXT,
    last_seen_version INTEGER,
    last_seen_ts TEXT,
    last_seen_etag TEXT
);
```

**Detection Logic:**

```python
def is_echo(remote_id: str, remote_version: int) -> bool:
    """Check if remote update is just echoing our write."""
    ledger_entry = get_ledger_entry(remote_id)
    
    if not ledger_entry:
        return False  # Never seen before
    
    # If remote version matches what we last pushed, it's an echo
    return remote_version <= ledger_entry.last_seen_version
```

**Processing:**

```python
# Kira→GCal export
push_to_gcal(event)
record_sync(event.remote_id, version=event.version, etag=response.etag)

# GCal→Kira import
if is_echo(gcal_event.id, gcal_event.version):
    logger.info("Echo detected, skipping", remote_id=gcal_event.id)
    return  # Break the loop

import_from_gcal(gcal_event)
record_sync(gcal_event.id, version=gcal_event.version)
```

### Conflict Resolution

**Policy: Latest-Wins**

```python
def resolve_conflict(local_ts: str, remote_ts: str) -> str:
    """Resolve conflict by timestamp."""
    local_dt = parse_utc_iso8601(local_ts)
    remote_dt = parse_utc_iso8601(remote_ts)
    
    if remote_dt > local_dt:
        return "remote"  # Remote wins
    else:
        return "local"   # Local wins (or tie)
```

## Consequences

### Positive

- **No echo loops**: Ledger prevents infinite sync cycles
- **Conflict resolution**: Clear policy (latest-wins)
- **Traceability**: Version history in metadata
- **Recovery**: Can rebuild ledger from entity metadata

### Negative

- **Complexity**: Sync logic is non-trivial
- **Storage**: Ledger database required
- **Latency**: Extra ledger lookups on import

### Trade-offs

- **Latest-wins**: Simple but may lose concurrent edits (acceptable for Kira's use case)
- **Alternative**: Operational transform (too complex for current needs)

## Implementation

### Sync Contract

```python
# src/kira/sync/contract.py

@dataclass
class SyncContract:
    source: str  # "kira" | "gcal"
    version: int
    remote_id: str | None
    last_write_ts: str  # ISO-8601 UTC
    etag: str | None

def create_kira_sync_contract(metadata: dict, remote_id: str | None = None) -> dict:
    """Create sync contract for Kira write."""
    current = get_sync_contract(metadata)
    
    return {
        **metadata,
        "x-kira": {
            "source": "kira",
            "version": (current.version if current else 0) + 1,
            "remote_id": remote_id or (current.remote_id if current else None),
            "last_write_ts": datetime.now(timezone.utc).isoformat(),
        }
    }
```

### Sync Ledger

```python
# src/kira/sync/ledger.py

class SyncLedger:
    def record_sync(self, remote_id: str, version: int, etag: str | None = None):
        """Record successful sync."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO sync_ledger (remote_id, last_seen_version, last_seen_ts, last_seen_etag)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (remote_id)
            DO UPDATE SET
                last_seen_version = ?,
                last_seen_ts = ?,
                last_seen_etag = ?
        """, (remote_id, version, now, etag, version, now, etag))
        self.conn.commit()
    
    def is_echo(self, remote_id: str, remote_version: int) -> bool:
        """Check if remote update is echo of our write."""
        cursor = self.conn.execute(
            "SELECT last_seen_version FROM sync_ledger WHERE remote_id = ?",
            (remote_id,)
        )
        row = cursor.fetchone()
        return row is not None and remote_version <= row[0]
```

## Verification

### DoD Check

```python
def test_echo_loop_prevention():
    """Test DoD: Kira→GCal→Kira results in single write."""
    # Kira creates event
    event = create_event("Team Meeting")
    assert event.x_kira.source == "kira"
    assert event.x_kira.version == 1
    
    # Export to GCal
    gcal_event = export_to_gcal(event)
    ledger.record_sync(gcal_event.id, version=event.x_kira.version)
    
    # GCal echoes back (no real change)
    assert ledger.is_echo(gcal_event.id, gcal_event.version)
    
    # Should NOT import (breaks loop)
    assert not ledger.should_import(gcal_event.id, gcal_event.version)
```

### Tests

- `tests/unit/test_sync_contract.py`: Contract logic (21 tests)
- `tests/unit/test_sync_ledger.py`: Ledger operations (22 tests)
- `tests/integration/test_gcal_sync_integration.py`: E2E sync (9 tests)

## References

- Implementation: `src/kira/sync/contract.py`, `src/kira/sync/ledger.py`
- Related: ADR-003 (Idempotency), ADR-005 (Timezone)
