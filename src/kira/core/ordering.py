"""Ordering tolerance and event sequencing (Phase 2, Point 10).

Grace buffer for out-of-order events + commutative idempotent reducers.
Handles "edit before create" and replays deterministically.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable

from .event_envelope import EventEnvelope
from .time import parse_utc_iso8601

__all__ = [
    "EventBuffer",
    "EventReducer",
    "ReducerRegistry",
    "create_event_buffer",
]


@dataclass
class BufferedEvent:
    """Event in the grace buffer."""
    
    envelope: EventEnvelope
    received_at: float  # Unix timestamp when received
    attempts: int = 0
    
    @property
    def age_seconds(self) -> float:
        """Get age of buffered event in seconds."""
        return time.time() - self.received_at


class EventReducer:
    """Base class for commutative idempotent reducers (Phase 2, Point 10).
    
    Reducers must be:
    1. Idempotent: Applying same event multiple times = applying once
    2. Commutative: Order of independent events doesn't matter
    3. Deterministic: Same input events always produce same output
    
    This enables handling out-of-order delivery, replays, and "edit before create".
    """
    
    def apply(self, state: dict[str, Any], envelope: EventEnvelope) -> dict[str, Any]:
        """Apply event to state, producing new state.
        
        Must be idempotent and commutative.
        
        Parameters
        ----------
        state
            Current state
        envelope
            Event to apply
            
        Returns
        -------
        dict[str, Any]
            New state after applying event
        """
        raise NotImplementedError("Subclasses must implement apply()")
    
    def can_apply(self, state: dict[str, Any], envelope: EventEnvelope) -> bool:
        """Check if event can be applied to current state.
        
        Used to determine if dependencies are met.
        
        Parameters
        ----------
        state
            Current state
        envelope
            Event to check
            
        Returns
        -------
        bool
            True if event can be applied
        """
        return True  # Default: always can apply


class ReducerRegistry:
    """Registry for event reducers."""
    
    def __init__(self) -> None:
        self._reducers: dict[str, EventReducer] = {}
    
    def register(self, event_type: str, reducer: EventReducer) -> None:
        """Register reducer for event type.
        
        Parameters
        ----------
        event_type
            Event type pattern (e.g., "task.*", "task.created")
        reducer
            Reducer instance
        """
        self._reducers[event_type] = reducer
    
    def get_reducer(self, event_type: str) -> EventReducer | None:
        """Get reducer for event type.
        
        Parameters
        ----------
        event_type
            Event type
            
        Returns
        -------
        EventReducer | None
            Reducer if registered, None otherwise
        """
        # Exact match
        if event_type in self._reducers:
            return self._reducers[event_type]
        
        # Wildcard match (e.g., "task.*")
        for pattern, reducer in self._reducers.items():
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if event_type.startswith(prefix + "."):
                    return reducer
        
        return None


class EventBuffer:
    """Grace buffer for out-of-order events (Phase 2, Point 10).
    
    Buffers events for a short grace period (e.g., 3-10s) to handle
    out-of-order delivery. Events are processed when:
    1. Grace period expires
    2. Dependencies are met
    3. Buffer is flushed
    
    Supports "edit before create" and deterministic replays.
    """
    
    def __init__(
        self,
        grace_period_seconds: float = 5.0,
        max_buffer_size: int = 1000,
    ) -> None:
        """Initialize event buffer.
        
        Parameters
        ----------
        grace_period_seconds
            Grace period for buffering (default 5s)
        max_buffer_size
            Maximum events to buffer
        """
        self.grace_period_seconds = grace_period_seconds
        self.max_buffer_size = max_buffer_size
        
        # Buffer events by entity_id for ordering
        self._buffers: dict[str, deque[BufferedEvent]] = defaultdict(deque)
        
        # Track processed event IDs (for idempotency)
        self._processed_ids: set[str] = set()
        
        # Reducer registry
        self._reducers = ReducerRegistry()
        
        # Statistics
        self._total_received = 0
        self._total_processed = 0
        self._total_reordered = 0
        self._total_buffered_peak = 0
    
    def register_reducer(self, event_type: str, reducer: EventReducer) -> None:
        """Register event reducer.
        
        Parameters
        ----------
        event_type
            Event type or pattern
        reducer
            Reducer instance
        """
        self._reducers.register(event_type, reducer)
    
    def add_event(self, envelope: EventEnvelope) -> bool:
        """Add event to buffer.
        
        Returns True if event is new (not a duplicate).
        
        Parameters
        ----------
        envelope
            Event envelope
            
        Returns
        -------
        bool
            True if event was added (not duplicate)
        """
        self._total_received += 1
        
        # Check for duplicate (idempotency)
        if envelope.event_id in self._processed_ids:
            return False  # Already processed
        
        # Check if already in buffer
        for buffer in self._buffers.values():
            for buffered in buffer:
                if buffered.envelope.event_id == envelope.event_id:
                    return False  # Already buffered
        
        # Extract entity ID from payload
        entity_id = self._extract_entity_id(envelope)
        
        # Add to buffer
        buffered = BufferedEvent(
            envelope=envelope,
            received_at=time.time(),
        )
        self._buffers[entity_id].append(buffered)
        
        # Update stats
        total_buffered = sum(len(buf) for buf in self._buffers.values())
        self._total_buffered_peak = max(self._total_buffered_peak, total_buffered)
        
        # Check buffer size limit
        if total_buffered > self.max_buffer_size:
            # Force flush oldest
            self._flush_oldest()
        
        return True
    
    def process_ready_events(
        self,
        state: dict[str, Any],
    ) -> tuple[dict[str, Any], list[EventEnvelope]]:
        """Process events that are ready.
        
        Events are ready when:
        1. Grace period has expired, OR
        2. Dependencies are met and can be applied immediately
        
        Parameters
        ----------
        state
            Current state
            
        Returns
        -------
        tuple[dict[str, Any], list[EventEnvelope]]
            (updated_state, processed_envelopes)
        """
        processed = []
        current_state = state.copy()
        
        # Check all buffers
        for entity_id, buffer in list(self._buffers.items()):
            if not buffer:
                continue
            
            # Sort buffer by timestamp and seq for deterministic processing
            sorted_events = self._sort_events(buffer)
            
            # Process events that are ready
            remaining = deque()
            for buffered in sorted_events:
                # Check if grace period expired or can apply immediately
                if self._should_process(buffered, current_state):
                    # Apply event
                    current_state = self._apply_event(current_state, buffered.envelope)
                    processed.append(buffered.envelope)
                    self._processed_ids.add(buffered.envelope.event_id)
                    self._total_processed += 1
                else:
                    # Keep in buffer
                    remaining.append(buffered)
            
            # Update buffer
            if remaining:
                self._buffers[entity_id] = remaining
            else:
                del self._buffers[entity_id]
        
        return current_state, processed
    
    def flush_all(self, state: dict[str, Any]) -> tuple[dict[str, Any], list[EventEnvelope]]:
        """Flush all buffered events immediately.
        
        Processes all events in deterministic order.
        
        Parameters
        ----------
        state
            Current state
            
        Returns
        -------
        tuple[dict[str, Any], list[EventEnvelope]]
            (updated_state, processed_envelopes)
        """
        processed = []
        current_state = state.copy()
        
        # Collect all events
        all_events = []
        for buffer in self._buffers.values():
            all_events.extend(buffer)
        
        # Sort globally by timestamp/seq
        sorted_events = self._sort_events(all_events)
        
        # Process all
        for buffered in sorted_events:
            if buffered.envelope.event_id not in self._processed_ids:
                current_state = self._apply_event(current_state, buffered.envelope)
                processed.append(buffered.envelope)
                self._processed_ids.add(buffered.envelope.event_id)
                self._total_processed += 1
        
        # Clear buffers
        self._buffers.clear()
        
        return current_state, processed
    
    def _extract_entity_id(self, envelope: EventEnvelope) -> str:
        """Extract entity ID from envelope for buffer grouping."""
        payload = envelope.payload
        
        # Try common ID fields
        for key in ["entity_id", "id", "task_id", "note_id", "event_id_field"]:
            if key in payload:
                return str(payload[key])
        
        # Fallback: use event type as grouping key
        return envelope.type
    
    def _should_process(self, buffered: BufferedEvent, state: dict[str, Any]) -> bool:
        """Check if event should be processed now."""
        # Grace period expired?
        if buffered.age_seconds >= self.grace_period_seconds:
            return True
        
        # For very short grace periods, respect the grace period
        # Only skip grace if dependencies are met AND there's significant buffering
        if self.grace_period_seconds > 0:
            # Can apply immediately only if dependencies are explicitly met
            # and grace period is long enough (> 1s) to justify early processing
            if self.grace_period_seconds > 1.0:
                reducer = self._reducers.get_reducer(buffered.envelope.type)
                if reducer and reducer.can_apply(state, buffered.envelope):
                    return True
        
        return False
    
    def _apply_event(self, state: dict[str, Any], envelope: EventEnvelope) -> dict[str, Any]:
        """Apply event to state using registered reducer."""
        reducer = self._reducers.get_reducer(envelope.type)
        
        if reducer:
            return reducer.apply(state, envelope)
        else:
            # No reducer: just track that we processed it
            return state
    
    def _sort_events(self, events: list[BufferedEvent] | deque[BufferedEvent]) -> list[BufferedEvent]:
        """Sort events for deterministic processing.
        
        Sort by:
        1. event_ts (timestamp from event)
        2. seq (sequence number, if present)
        3. event_id (for tie-breaking)
        """
        def sort_key(buffered: BufferedEvent) -> tuple:
            envelope = buffered.envelope
            
            # Parse timestamp
            try:
                dt = parse_utc_iso8601(envelope.event_ts)
                ts = dt.timestamp()
            except (ValueError, AttributeError):
                ts = buffered.received_at
            
            # Get sequence number
            seq = envelope.seq if envelope.seq is not None else 0
            
            return (ts, seq, envelope.event_id)
        
        return sorted(events, key=sort_key)
    
    def _flush_oldest(self) -> None:
        """Flush oldest event to stay within buffer size limit."""
        # Find oldest event across all buffers
        oldest_buffered = None
        oldest_entity_id = None
        oldest_age = -1.0
        
        for entity_id, buffer in self._buffers.items():
            if buffer:
                buffered = buffer[0]
                if oldest_buffered is None or buffered.age_seconds > oldest_age:
                    oldest_buffered = buffered
                    oldest_entity_id = entity_id
                    oldest_age = buffered.age_seconds
        
        # Remove oldest
        if oldest_entity_id and oldest_buffered:
            self._buffers[oldest_entity_id].popleft()
            if not self._buffers[oldest_entity_id]:
                del self._buffers[oldest_entity_id]
    
    def get_stats(self) -> dict[str, Any]:
        """Get buffer statistics.
        
        Returns
        -------
        dict[str, Any]
            Statistics
        """
        total_buffered = sum(len(buf) for buf in self._buffers.values())
        
        return {
            "total_received": self._total_received,
            "total_processed": self._total_processed,
            "total_reordered": self._total_reordered,
            "currently_buffered": total_buffered,
            "buffered_peak": self._total_buffered_peak,
            "unique_entities": len(self._buffers),
            "processing_rate": (
                self._total_processed / self._total_received
                if self._total_received > 0
                else 0.0
            ),
        }


def create_event_buffer(
    grace_period_seconds: float = 5.0,
    max_buffer_size: int = 1000,
) -> EventBuffer:
    """Create event buffer with grace period.
    
    Parameters
    ----------
    grace_period_seconds
        Grace period for buffering (default 5s, range 3-10s recommended)
    max_buffer_size
        Maximum events to buffer
        
    Returns
    -------
    EventBuffer
        Configured event buffer
    """
    return EventBuffer(
        grace_period_seconds=grace_period_seconds,
        max_buffer_size=max_buffer_size,
    )

