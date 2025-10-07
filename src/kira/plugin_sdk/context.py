"""Runtime execution context exposed to plugins.

The concrete host injects instances of these helpers. The default in-memory
implementations are intentionally simple so that contract tests can exercise
expected behaviour without requiring the real infrastructure.

Note: The host can inject real EventBus and Scheduler implementations from
kira.core.events and kira.core.scheduler to replace the mock implementations.

Example:
    from kira.plugin_sdk.context import PluginContext

    context = PluginContext(config={"feature": "beta"})
    context.logger.info("Plugin activated")
    context.kv.set("seen", True)

Example with real implementations:
    from kira.core.events import create_event_bus
    from kira.core.scheduler import create_scheduler
    from kira.plugin_sdk.context import PluginContext

    real_bus = create_event_bus()
    real_scheduler = create_scheduler()

    context = PluginContext(
        config={"feature": "beta"},
        events=real_bus,
        scheduler=real_scheduler
    )
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .types import EventHandler, EventPayload

__all__ = [
    "EventBus",
    "EventBusProtocol",
    "KeyValueStore",
    "Logger",
    "PluginContext",
    "Scheduler",
    "SchedulerProtocol",
    "SecretsManager",
    "VaultProtocol",
]


class VaultProtocol(Protocol):
    """Protocol for Vault API implementations.

    This protocol is satisfied by the Host API from kira.core.host,
    ensuring plugins can access Vault operations through ctx.vault.
    """

    def create_entity(self, entity_type: str, data: dict[str, Any], *, content: str = "") -> Any:
        """Create new entity in Vault."""
        ...

    def read_entity(self, entity_id: str) -> Any:
        """Read entity by ID."""
        ...

    def update_entity(self, entity_id: str, updates: dict[str, Any], *, content: str | None = None) -> Any:
        """Update existing entity."""
        ...

    def delete_entity(self, entity_id: str) -> None:
        """Delete entity from Vault."""
        ...

    def list_entities(self, entity_type: str | None = None, *, limit: int | None = None) -> Any:
        """List entities in Vault."""
        ...


class EventBusProtocol(Protocol):
    """Protocol for event bus implementations.

    This protocol is satisfied by both the mock EventBus below and the
    real EventBus from kira.core.events, ensuring compatibility.
    """

    def publish(self, event_name: str, data: EventPayload = None) -> Any:
        """Publish event to subscribers."""
        ...

    def subscribe(self, event_name: str, handler: EventHandler[EventPayload]) -> Any:
        """Subscribe handler to event."""
        ...


class SchedulerProtocol(Protocol):
    """Protocol for scheduler implementations.

    This protocol is satisfied by both the mock Scheduler below and the
    real Scheduler from kira.core.scheduler, ensuring compatibility.
    """

    def schedule_once(self, delay_seconds: int, task: Callable[[], None]) -> str:
        """Schedule task to run once after delay."""
        ...

    def schedule_recurring(self, interval_seconds: int, task: Callable[[], None]) -> str:
        """Schedule recurring task."""
        ...

    def cancel(self, task_id: str) -> bool:
        """Cancel scheduled task."""
        ...


class EventBus:
    """Light-weight pub/sub façade available to plugins.

    Example:
        >>> from kira.plugin_sdk.context import EventBus
        >>> bus = EventBus()
        >>> events: list[tuple[str, dict[str, str]]] = []
        >>> bus.subscribe("task.created", lambda ctx, payload: events.append((ctx.config["event"], payload or {})))
        >>> bus.publish("task.created", {"id": "42"})
        >>> events[0]
        ('task.created', {'id': '42'})
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler[EventPayload]]] = defaultdict(list)

    def publish(self, event_name: str, data: EventPayload = None) -> None:
        """Deliver ``data`` to every subscriber registered for ``event_name``."""

        context = PluginContext(config={"event": event_name}, events=self)
        for handler in self._subscribers.get(event_name, []):
            result = handler(context, data)
            if hasattr(result, "__await__"):
                raise RuntimeError(
                    "Async handlers are not supported by the default EventBus mock."
                )

    def subscribe(self, event_name: str, handler: EventHandler[EventPayload]) -> None:
        """Register ``handler`` to be invoked when ``event_name`` is published."""

        self._subscribers[event_name].append(handler)


class Logger:
    """Structured logger façade for plugin authors.

    The implementation uses ``print`` for determinism in tests. Hosts can
    provide richer integrations (e.g. JSON logging) while keeping the API
    stable for plugin authors.
    """

    def info(self, message: str) -> None:
        """Log an informational ``message``."""

        print(f"ℹ️  {message}")

    def warning(self, message: str) -> None:
        """Log a warning ``message``."""

        print(f"⚠️  {message}")

    def error(self, message: str) -> None:
        """Log an error ``message``."""

        print(f"❌ {message}")

    def debug(self, message: str) -> None:
        """Log a debug ``message`` for verbose traces."""

        print(f"🐛 {message}")


class Scheduler:
    """In-memory scheduler façade exposing the minimal scheduling API."""

    def __init__(self) -> None:
        self._tasks: dict[str, Callable[[], None]] = {}

    def schedule_once(self, delay_seconds: int, task: Callable[[], None]) -> str:
        """Register ``task`` to execute once after ``delay_seconds``.

        Returns a scheduler identifier that can later be cancelled.
        """

        task_id = f"task_{delay_seconds}_{len(self._tasks)}"
        self._tasks[task_id] = task
        print(f"⏰ Scheduled task: {task_id}")
        return task_id

    def schedule_recurring(self, interval_seconds: int, task: Callable[[], None]) -> str:
        """Register ``task`` to run every ``interval_seconds`` seconds."""

        task_id = f"recurring_{interval_seconds}_{len(self._tasks)}"
        self._tasks[task_id] = task
        print(f"🔄 Scheduled recurring task: {task_id}")
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task if it exists."""

        existed = task_id in self._tasks
        self._tasks.pop(task_id, None)
        if existed:
            print(f"❌ Cancelled task: {task_id}")
        return existed


class KeyValueStore:
    """In-memory key/value helper mirroring the host storage contract."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Return the value stored under ``key`` or ``default`` when missing."""

        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key`` and emit a trace for tests."""

        self._store[key] = value
        print(f"💾 Stored {key} = {value}")

    def delete(self, key: str) -> bool:
        """Remove ``key`` from the store if present."""

        if key in self._store:
            del self._store[key]
            print(f"🗑️  Deleted: {key}")
            return True
        return False


class SecretsManager:
    """Facade to request and manage secrets.

    The default implementation acts as an in-memory placeholder. Hosts should
    replace it with secure backends such as Vault or AWS Secrets Manager.
    """

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        """Return the secret value stored under ``key``."""

        print(f"🔐 Requested secret: {key}")
        return self._secrets.get(key)

    def set(self, key: str, value: str) -> None:
        """Persist a secret value for ``key``."""

        print(f"🔐 Stored secret: {key}")
        self._secrets[key] = value

    def delete(self, key: str) -> bool:
        """Delete the secret identified by ``key`` if present."""

        existed = key in self._secrets
        self._secrets.pop(key, None)
        if existed:
            print(f"🔐 Deleted secret: {key}")
        return existed


class PluginContext:
    """Aggregate runtime helpers made available to plugins.

    The context is the primary object handed to plugin entry points. It
    provides access to the event bus, logger, scheduler, key/value store and
    secrets manager.

    The host can inject real implementations from kira.core to replace the
    default mock implementations used for testing.
    """

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        events: EventBusProtocol | EventBus | None = None,
        logger: Logger | None = None,
        scheduler: SchedulerProtocol | Scheduler | None = None,
        kv: KeyValueStore | None = None,
        secrets: SecretsManager | None = None,
        vault: VaultProtocol | None = None,
    ) -> None:
        self.config: Mapping[str, Any] = config or {}
        self.events: EventBusProtocol = events if events is not None else EventBus()
        self.logger = logger or Logger()
        self.scheduler: SchedulerProtocol = scheduler if scheduler is not None else Scheduler()
        self.kv = kv or KeyValueStore()
        self.secrets = secrets or SecretsManager()
        self.vault: VaultProtocol | None = vault  # None means no Vault access

    def with_overrides(
        self,
        **overrides: Any,
    ) -> PluginContext:
        """Return a shallow copy of the context replacing provided attributes."""

        return PluginContext(
            config=overrides.get("config", self.config),
            events=overrides.get("events", self.events),
            logger=overrides.get("logger", self.logger),
            scheduler=overrides.get("scheduler", self.scheduler),
            kv=overrides.get("kv", self.kv),
            secrets=overrides.get("secrets", self.secrets),
            vault=overrides.get("vault", self.vault),
        )
