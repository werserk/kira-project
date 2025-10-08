"""Event bus implementation for reactive architecture (ADR-005).

Provides lightweight in-process pub/sub with retry policies, filtering,
correlation IDs, and structured logging.
"""

from __future__ import annotations

import time
import traceback
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Event",
    "EventBus",
    "EventHandler",
    "HandlerResult",
    "RetryPolicy",
    "SubscriptionHandle",
]


@dataclass
class RetryPolicy:
    """Retry policy for event handlers."""

    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True


@dataclass
class Event:
    """Event container with metadata."""

    name: str
    payload: dict[str, Any] | None = None
    headers: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str | None = None  # ADR-015: trace propagation
    timestamp: float = field(default_factory=time.time)

    def with_correlation_id(self, correlation_id: str) -> Event:
        """Create new event with specified correlation ID."""
        return Event(
            name=self.name,
            payload=self.payload,
            headers=self.headers.copy(),
            correlation_id=correlation_id,
            trace_id=self.trace_id,
            timestamp=self.timestamp,
        )

    def with_trace_id(self, trace_id: str) -> Event:
        """Create new event with specified trace ID (ADR-015)."""
        return Event(
            name=self.name,
            payload=self.payload,
            headers=self.headers.copy(),
            correlation_id=self.correlation_id,
            trace_id=trace_id,
            timestamp=self.timestamp,
        )


EventHandler = Callable[[Event], Any]
"""Type alias for event handler functions."""

FilterPredicate = Callable[[Event], bool]
"""Type alias for event filter predicates."""


@dataclass
class HandlerResult:
    """Result of handler execution."""

    success: bool
    duration_ms: float
    error: Exception | None = None
    attempts: int = 1


@dataclass
class SubscriptionHandle:
    """Handle for managing subscriptions."""

    subscription_id: str
    event_name: str
    handler: EventHandler
    filter_predicate: FilterPredicate | None = None
    once: bool = False
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    _triggered: bool = field(default=False, init=False)

    def should_handle(self, event: Event) -> bool:
        """Check if this subscription should handle the event."""
        if self.once and self._triggered:
            return False

        return not (self.filter_predicate and not self.filter_predicate(event))

    def mark_triggered(self) -> None:
        """Mark subscription as triggered (for once=True)."""
        self._triggered = True


class EventBus:
    """Lightweight in-process event bus with pub/sub (ADR-005).

    Features:
    - Synchronous delivery by default for determinism
    - Retry policies with exponential backoff and jitter
    - Filter predicates for selective handling
    - Correlation IDs for request tracing
    - Structured logging (when logger provided)

    Example:
        >>> bus = EventBus()
        >>> def handler(event):
        ...     print(f"Received: {event.name}")
        >>> handle = bus.subscribe("task.created", handler)
        >>> bus.publish("task.created", {"id": "task-123"})
        Received: task.created
    """

    def __init__(self, logger: Any = None) -> None:
        """Initialize event bus.

        Parameters
        ----------
        logger
            Optional logger for structured logging
        """
        self._subscriptions: dict[str, list[SubscriptionHandle]] = defaultdict(list)
        self._logger = logger
        self._delivery_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"published": 0, "delivered": 0, "failed": 0}
        )

    def publish(
        self,
        event_name: str,
        payload: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> int:
        """Publish event to all subscribers.

        Parameters
        ----------
        event_name
            Dot-separated event name (e.g., "task.created")
        payload
            Event payload data
        headers
            Optional metadata headers
        correlation_id
            Optional correlation ID for tracing (generated if not provided)

        Returns
        -------
        int
            Number of handlers that received the event
        """
        # Create event
        event = Event(
            name=event_name,
            payload=payload or {},
            headers=headers or {},
            correlation_id=correlation_id or str(uuid.uuid4()),
            timestamp=time.time(),
        )

        # Log publication
        if self._logger:
            self._logger.info(
                f"Event published: {event_name}",
                extra={
                    "event_name": event_name,
                    "correlation_id": event.correlation_id,
                    "payload_keys": list(event.payload.keys()) if event.payload else [],
                },
            )

        self._delivery_stats[event_name]["published"] += 1

        # Deliver to subscribers
        handlers_triggered = 0
        subscriptions = self._subscriptions.get(event_name, [])

        for subscription in subscriptions[:]:  # Copy to allow modification during iteration
            if not subscription.should_handle(event):
                continue

            result = self._deliver_to_handler(subscription, event)

            if result.success:
                self._delivery_stats[event_name]["delivered"] += 1
                handlers_triggered += 1

                if subscription.once:
                    subscription.mark_triggered()
                    self._subscriptions[event_name].remove(subscription)
            else:
                self._delivery_stats[event_name]["failed"] += 1

        return handlers_triggered

    def subscribe(
        self,
        event_name: str,
        handler: EventHandler,
        *,
        filter_predicate: FilterPredicate | None = None,
        once: bool = False,
        retry_policy: RetryPolicy | None = None,
    ) -> SubscriptionHandle:
        """Subscribe to events.

        Parameters
        ----------
        event_name
            Event name pattern to subscribe to
        handler
            Handler function (takes Event, returns Any)
        filter_predicate
            Optional filter predicate (takes Event, returns bool)
        once
            If True, handler is called only once then unsubscribed
        retry_policy
            Optional retry policy for failed handlers

        Returns
        -------
        SubscriptionHandle
            Handle for managing the subscription
        """
        subscription = SubscriptionHandle(
            subscription_id=str(uuid.uuid4()),
            event_name=event_name,
            handler=handler,
            filter_predicate=filter_predicate,
            once=once,
            retry_policy=retry_policy or RetryPolicy(),
        )

        self._subscriptions[event_name].append(subscription)

        if self._logger:
            self._logger.debug(
                f"Subscription created for {event_name}",
                extra={
                    "event_name": event_name,
                    "subscription_id": subscription.subscription_id,
                    "once": once,
                },
            )

        return subscription

    def unsubscribe(self, handle: SubscriptionHandle) -> bool:
        """Unsubscribe handler.

        Parameters
        ----------
        handle
            Subscription handle to remove

        Returns
        -------
        bool
            True if subscription was found and removed
        """
        subscriptions = self._subscriptions.get(handle.event_name, [])

        # Find and remove the subscription (filter out matching subscription)
        initial_count = len(subscriptions)
        self._subscriptions[handle.event_name] = [
            sub for sub in subscriptions if sub.subscription_id != handle.subscription_id
        ]

        removed = len(self._subscriptions[handle.event_name]) < initial_count

        if removed and self._logger:
            self._logger.debug(
                f"Subscription removed: {handle.subscription_id}",
                extra={"subscription_id": handle.subscription_id},
            )

        return removed

    def unsubscribe_all(self, event_name: str) -> int:
        """Remove all subscriptions for event name.

        Parameters
        ----------
        event_name
            Event name

        Returns
        -------
        int
            Number of subscriptions removed
        """
        count = len(self._subscriptions.get(event_name, []))
        if event_name in self._subscriptions:
            del self._subscriptions[event_name]

        if self._logger and count > 0:
            self._logger.debug(
                f"Removed all subscriptions for {event_name}",
                extra={"event_name": event_name, "count": count},
            )

        return count

    def clear(self) -> None:
        """Remove all subscriptions."""
        self._subscriptions.clear()
        self._delivery_stats.clear()

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Get delivery statistics.

        Returns
        -------
        dict
            Statistics by event name
        """
        return dict(self._delivery_stats)

    def get_subscriptions(self, event_name: str | None = None) -> list[SubscriptionHandle]:
        """Get current subscriptions.

        Parameters
        ----------
        event_name
            Optional event name to filter by

        Returns
        -------
        list[SubscriptionHandle]
            List of subscription handles
        """
        if event_name:
            return self._subscriptions.get(event_name, [])[:]

        # Return all subscriptions
        result: list[SubscriptionHandle] = []
        for subscriptions in self._subscriptions.values():
            result.extend(subscriptions)
        return result

    def _deliver_to_handler(self, subscription: SubscriptionHandle, event: Event) -> HandlerResult:
        """Deliver event to handler with retry logic.

        Parameters
        ----------
        subscription
            Subscription handle
        event
            Event to deliver

        Returns
        -------
        HandlerResult
            Result of delivery
        """
        policy = subscription.retry_policy
        last_error: Exception | None = None
        attempts = 0
        start_time = time.time()

        for attempt in range(policy.max_attempts):
            attempts = attempt + 1

            try:
                # Call handler
                subscription.handler(event)

                duration_ms = (time.time() - start_time) * 1000

                if self._logger:
                    self._logger.debug(
                        f"Handler executed successfully: {event.name}",
                        extra={
                            "event_name": event.name,
                            "correlation_id": event.correlation_id,
                            "duration_ms": duration_ms,
                            "attempts": attempts,
                        },
                    )

                return HandlerResult(success=True, duration_ms=duration_ms, attempts=attempts)

            except Exception as exc:
                last_error = exc

                if attempt < policy.max_attempts - 1:
                    # Calculate delay with exponential backoff
                    delay = min(
                        policy.initial_delay * (policy.backoff_multiplier**attempt),
                        policy.max_delay,
                    )

                    # Add jitter if enabled
                    if policy.jitter:
                        import random

                        delay *= random.uniform(0.5, 1.5)

                    if self._logger:
                        self._logger.warning(
                            f"Handler failed (attempt {attempts}/{policy.max_attempts}), retrying in {delay:.2f}s",
                            extra={
                                "event_name": event.name,
                                "correlation_id": event.correlation_id,
                                "attempt": attempts,
                                "max_attempts": policy.max_attempts,
                                "delay_seconds": delay,
                                "error": str(exc),
                            },
                        )

                    time.sleep(delay)
                else:
                    # All retries exhausted
                    duration_ms = (time.time() - start_time) * 1000

                    if self._logger:
                        self._logger.error(
                            f"Handler failed after {attempts} attempts: {event.name}",
                            extra={
                                "event_name": event.name,
                                "correlation_id": event.correlation_id,
                                "attempts": attempts,
                                "duration_ms": duration_ms,
                                "error": str(exc),
                                "traceback": traceback.format_exc(),
                            },
                        )

        duration_ms = (time.time() - start_time) * 1000
        return HandlerResult(success=False, duration_ms=duration_ms, error=last_error, attempts=attempts)


def create_event_bus(logger: Any = None) -> EventBus:
    """Factory function to create event bus.

    Parameters
    ----------
    logger
        Optional logger instance

    Returns
    -------
    EventBus
        Configured event bus
    """
    return EventBus(logger=logger)
