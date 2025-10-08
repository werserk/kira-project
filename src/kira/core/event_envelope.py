"""Standardized event envelope (Phase 2, Point 9).

Unified event envelope: {event_id, event_ts, seq?, source, type, payload}
Delivery is at-least-once; consumers must be idempotent by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .idempotency import generate_event_id
from .time import format_utc_iso8601, get_current_utc, parse_utc_iso8601

__all__ = [
    "EventEnvelope",
    "create_event_envelope",
    "validate_event_envelope",
]


@dataclass
class EventEnvelope:
    """Standardized event envelope (Phase 2, Point 9).
    
    Unified structure for all events across producers/consumers.
    Delivery is at-least-once; consumers must be idempotent.
    
    Attributes
    ----------
    event_id : str
        Unique event identifier (for deduplication)
    event_ts : str
        Event timestamp (ISO-8601 UTC)
    source : str
        Event source (telegram, gcal, cli, internal)
    type : str
        Event type (e.g., "message.received", "task.created")
    payload : dict[str, Any]
        Event payload (normalized)
    seq : int | None
        Optional sequence number (for ordering)
    correlation_id : str | None
        Optional correlation ID (for tracing)
    metadata : dict[str, Any]
        Optional additional metadata
    """
    
    event_id: str
    event_ts: str
    source: str
    type: str
    payload: dict[str, Any]
    seq: int | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert envelope to dict for serialization.
        
        Returns
        -------
        dict[str, Any]
            Envelope as dictionary
        """
        result = {
            "event_id": self.event_id,
            "event_ts": self.event_ts,
            "source": self.source,
            "type": self.type,
            "payload": self.payload,
        }
        
        # Optional fields
        if self.seq is not None:
            result["seq"] = self.seq
        if self.correlation_id is not None:
            result["correlation_id"] = self.correlation_id
        if self.metadata:
            result["metadata"] = self.metadata
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventEnvelope:
        """Create envelope from dict.
        
        Parameters
        ----------
        data
            Dictionary with envelope fields
            
        Returns
        -------
        EventEnvelope
            Created envelope
        """
        return cls(
            event_id=data["event_id"],
            event_ts=data["event_ts"],
            source=data["source"],
            type=data["type"],
            payload=data["payload"],
            seq=data.get("seq"),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


def create_event_envelope(
    source: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    external_id: str | None = None,
    seq: int | None = None,
    correlation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EventEnvelope:
    """Create standardized event envelope (Phase 2, Point 9).
    
    Generates event_id using sha256(source, external_id, payload).
    Sets event_ts to current UTC.
    
    Parameters
    ----------
    source
        Event source (telegram, gcal, cli, internal)
    event_type
        Event type (e.g., "message.received")
    payload
        Event payload (should be normalized)
    external_id
        External identifier (for ID generation)
    seq
        Optional sequence number
    correlation_id
        Optional correlation ID
    metadata
        Optional metadata
        
    Returns
    -------
    EventEnvelope
        Created envelope
        
    Example
    -------
    >>> payload = {"text": "Hello", "user_id": 123}
    >>> envelope = create_event_envelope(
    ...     source="telegram",
    ...     event_type="message.received",
    ...     payload=payload,
    ...     external_id="msg-456",
    ... )
    >>> envelope.source
    'telegram'
    """
    # Generate event ID
    ext_id = external_id or payload.get("external_id", "")
    event_id = generate_event_id(source, ext_id, payload)
    
    # Get current UTC timestamp
    event_ts = format_utc_iso8601(get_current_utc())
    
    return EventEnvelope(
        event_id=event_id,
        event_ts=event_ts,
        source=source,
        type=event_type,
        payload=payload,
        seq=seq,
        correlation_id=correlation_id,
        metadata=metadata or {},
    )


def validate_event_envelope(envelope: dict[str, Any] | EventEnvelope) -> list[str]:
    """Validate event envelope structure (Phase 2, Point 9).
    
    Checks for required fields and valid formats.
    
    Parameters
    ----------
    envelope
        Envelope to validate (dict or EventEnvelope)
        
    Returns
    -------
    list[str]
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Convert to dict if needed
    if isinstance(envelope, EventEnvelope):
        data = envelope.to_dict()
    else:
        data = envelope
    
    # Check required fields
    required_fields = ["event_id", "event_ts", "source", "type", "payload"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
        elif data[field] is None:
            errors.append(f"Field '{field}' cannot be null")
    
    # Validate payload is dict
    if "payload" in data and not isinstance(data["payload"], dict):
        errors.append(f"Field 'payload' must be dict, got {type(data['payload']).__name__}")
    
    # Validate event_ts is valid ISO-8601 UTC
    if "event_ts" in data:
        try:
            dt = parse_utc_iso8601(data["event_ts"])
            # Check if it's actually UTC
            if not data["event_ts"].endswith("+00:00") and not data["event_ts"].endswith("Z"):
                errors.append(f"event_ts must be in UTC (ISO-8601 with +00:00 or Z)")
        except (ValueError, AttributeError) as exc:
            errors.append(f"Invalid event_ts format: {exc}")
    
    # Validate seq is int if present
    if "seq" in data and data["seq"] is not None:
        if not isinstance(data["seq"], int):
            errors.append(f"Field 'seq' must be int, got {type(data['seq']).__name__}")
    
    # Validate metadata is dict if present
    if "metadata" in data and data["metadata"] is not None:
        if not isinstance(data["metadata"], dict):
            errors.append(f"Field 'metadata' must be dict, got {type(data['metadata']).__name__}")
    
    return errors


def envelope_for_at_least_once_delivery(envelope: EventEnvelope) -> dict[str, Any]:
    """Prepare envelope for at-least-once delivery.
    
    Documents that delivery is at-least-once and consumers
    must be idempotent by design.
    
    Parameters
    ----------
    envelope
        Event envelope
        
    Returns
    -------
    dict[str, Any]
        Envelope dict with delivery semantics metadata
    """
    data = envelope.to_dict()
    
    # Add delivery semantics to metadata
    if "metadata" not in data:
        data["metadata"] = {}
    
    data["metadata"]["delivery_semantics"] = "at-least-once"
    data["metadata"]["requires_idempotent_consumer"] = True
    
    return data


def extract_event_for_processing(
    envelope: EventEnvelope,
) -> tuple[str, dict[str, Any]]:
    """Extract event type and payload for processing.
    
    Convenience method for consumers to extract the event data.
    
    Parameters
    ----------
    envelope
        Event envelope
        
    Returns
    -------
    tuple[str, dict[str, Any]]
        (event_type, payload)
    """
    return envelope.type, envelope.payload

