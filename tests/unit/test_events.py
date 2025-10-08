"""Tests for Event Bus implementation (ADR-005)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.events import Event, EventBus, RetryPolicy, SubscriptionHandle, create_event_bus


class TestEvent:
    def test_event_creation(self):
        """Test creating event with defaults."""
        event = Event(name="test.event", payload={"key": "value"})

        assert event.name == "test.event"
        assert event.payload == {"key": "value"}
        assert len(event.correlation_id) > 0
        assert event.timestamp > 0

    def test_event_with_correlation_id(self):
        """Test creating event with specific correlation ID."""
        event = Event(name="test.event")
        new_event = event.with_correlation_id("custom-id")

        assert new_event.correlation_id == "custom-id"
        assert new_event.name == event.name


class TestRetryPolicy:
    def test_default_retry_policy(self):
        """Test default retry policy."""
        policy = RetryPolicy()

        assert policy.max_attempts == 3
        assert policy.initial_delay == 1.0
        assert policy.backoff_multiplier == 2.0
        assert policy.jitter is True

    def test_custom_retry_policy(self):
        """Test custom retry policy."""
        policy = RetryPolicy(max_attempts=5, initial_delay=0.5, jitter=False)

        assert policy.max_attempts == 5
        assert policy.initial_delay == 0.5
        assert policy.jitter is False


class TestSubscriptionHandle:
    def test_should_handle_basic(self):
        """Test basic should_handle check."""
        handle = SubscriptionHandle(
            subscription_id="sub-1",
            event_name="test.event",
            handler=lambda e: None,
        )
        event = Event(name="test.event")

        assert handle.should_handle(event) is True

    def test_should_handle_once(self):
        """Test once subscription."""
        handle = SubscriptionHandle(
            subscription_id="sub-1",
            event_name="test.event",
            handler=lambda e: None,
            once=True,
        )
        event = Event(name="test.event")

        assert handle.should_handle(event) is True
        handle.mark_triggered()
        assert handle.should_handle(event) is False

    def test_should_handle_filter(self):
        """Test filtered subscription."""
        handle = SubscriptionHandle(
            subscription_id="sub-1",
            event_name="test.event",
            handler=lambda e: None,
            filter_predicate=lambda e: e.payload.get("type") == "important",
        )

        event_pass = Event(name="test.event", payload={"type": "important"})
        event_fail = Event(name="test.event", payload={"type": "normal"})

        assert handle.should_handle(event_pass) is True
        assert handle.should_handle(event_fail) is False


class TestEventBus:
    def test_create_event_bus(self):
        """Test creating event bus."""
        bus = EventBus()

        assert bus is not None
        assert len(bus.get_subscriptions()) == 0

    def test_publish_subscribe(self):
        """Test basic publish/subscribe."""
        bus = EventBus()
        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        bus.subscribe("test.event", handler)
        count = bus.publish("test.event", {"data": "value"})

        assert count == 1
        assert len(received_events) == 1
        assert received_events[0].name == "test.event"
        assert received_events[0].payload["data"] == "value"

    def test_multiple_subscribers(self):
        """Test multiple subscribers for same event."""
        bus = EventBus()
        calls: list[str] = []

        bus.subscribe("test.event", lambda e: calls.append("handler1"))
        bus.subscribe("test.event", lambda e: calls.append("handler2"))

        count = bus.publish("test.event")

        assert count == 2
        assert calls == ["handler1", "handler2"]

    def test_subscribe_once(self):
        """Test once subscription."""
        bus = EventBus()
        calls: list[int] = []

        bus.subscribe("test.event", lambda e: calls.append(1), once=True)

        bus.publish("test.event")
        bus.publish("test.event")

        assert len(calls) == 1

    def test_subscribe_with_filter(self):
        """Test filtered subscription."""
        bus = EventBus()
        received: list[Event] = []

        bus.subscribe(
            "test.event",
            lambda e: received.append(e),
            filter_predicate=lambda e: e.payload.get("important") is True,
        )

        bus.publish("test.event", {"important": True, "data": "A"})
        bus.publish("test.event", {"important": False, "data": "B"})
        bus.publish("test.event", {"important": True, "data": "C"})

        assert len(received) == 2
        assert received[0].payload["data"] == "A"
        assert received[1].payload["data"] == "C"

    def test_unsubscribe(self):
        """Test unsubscribing handler."""
        bus = EventBus()
        calls: list[int] = []

        handle = bus.subscribe("test.event", lambda e: calls.append(1))

        bus.publish("test.event")
        assert len(calls) == 1

        bus.unsubscribe(handle)
        bus.publish("test.event")
        assert len(calls) == 1

    def test_unsubscribe_all(self):
        """Test unsubscribing all handlers for event."""
        bus = EventBus()

        bus.subscribe("test.event", lambda e: None)
        bus.subscribe("test.event", lambda e: None)
        bus.subscribe("other.event", lambda e: None)

        count = bus.unsubscribe_all("test.event")

        assert count == 2
        assert len(bus.get_subscriptions("test.event")) == 0
        assert len(bus.get_subscriptions("other.event")) == 1

    def test_clear(self):
        """Test clearing all subscriptions."""
        bus = EventBus()

        bus.subscribe("event1", lambda e: None)
        bus.subscribe("event2", lambda e: None)

        bus.clear()

        assert len(bus.get_subscriptions()) == 0

    def test_get_subscriptions(self):
        """Test getting subscriptions."""
        bus = EventBus()

        bus.subscribe("event1", lambda e: None)
        bus.subscribe("event1", lambda e: None)
        bus.subscribe("event2", lambda e: None)

        all_subs = bus.get_subscriptions()
        event1_subs = bus.get_subscriptions("event1")

        assert len(all_subs) == 3
        assert len(event1_subs) == 2

    def test_get_stats(self):
        """Test delivery statistics."""
        bus = EventBus()

        bus.subscribe("test.event", lambda e: None)
        bus.publish("test.event")
        bus.publish("test.event")

        stats = bus.get_stats()

        assert stats["test.event"]["published"] == 2
        assert stats["test.event"]["delivered"] == 2

    def test_handler_exception_retry(self):
        """Test handler exception with retry."""
        bus = EventBus()
        attempts: list[int] = []

        def failing_handler(event: Event) -> None:
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("Test error")

        policy = RetryPolicy(max_attempts=3, initial_delay=0.1, jitter=False)
        bus.subscribe("test.event", failing_handler, retry_policy=policy)

        bus.publish("test.event")

        assert len(attempts) == 3

    def test_handler_exhausted_retries(self):
        """Test handler with exhausted retries."""
        bus = EventBus()
        attempts: list[int] = []

        def always_failing(event: Event) -> None:
            attempts.append(1)
            raise ValueError("Always fails")

        policy = RetryPolicy(max_attempts=2, initial_delay=0.05, jitter=False)
        bus.subscribe("test.event", always_failing, retry_policy=policy)

        count = bus.publish("test.event")

        assert len(attempts) == 2
        assert count == 0  # Failed delivery

        stats = bus.get_stats()
        assert stats["test.event"]["failed"] == 1

    def test_correlation_id_propagation(self):
        """Test correlation ID is propagated."""
        bus = EventBus()
        received_events: list[Event] = []

        bus.subscribe("test.event", lambda e: received_events.append(e))

        correlation_id = "custom-correlation-id"
        bus.publish("test.event", correlation_id=correlation_id)

        assert received_events[0].correlation_id == correlation_id


class TestEventBusFactory:
    def test_create_event_bus(self):
        """Test factory function."""
        bus = create_event_bus()

        assert isinstance(bus, EventBus)
