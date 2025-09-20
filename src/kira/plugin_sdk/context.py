"""Runtime execution context exposed to plugins.

The concrete host injects instances of these helpers. The default in-memory
implementations are intentionally simple so that contract tests can exercise
expected behaviour without requiring the real infrastructure.

Example:
    from kira.plugin_sdk.context import PluginContext

    context = PluginContext(config={"feature": "beta"})
    context.logger.info("Plugin activated")
    context.kv.set("seen", True)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

from .types import EventHandler, EventPayload

__all__ = [
    "PluginContext",
    "EventBus",
    "Logger",
    "Scheduler",
    "KeyValueStore",
    "SecretsManager",
]


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
    """

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        events: EventBus | None = None,
        logger: Logger | None = None,
        scheduler: Scheduler | None = None,
        kv: KeyValueStore | None = None,
        secrets: SecretsManager | None = None,
    ) -> None:
        self.config: Mapping[str, Any] = config or {}
        self.events = events or EventBus()
        self.logger = logger or Logger()
        self.scheduler = scheduler or Scheduler()
        self.kv = kv or KeyValueStore()
        self.secrets = secrets or SecretsManager()

    def with_overrides(
        self,
        **overrides: Any,
    ) -> "PluginContext":
        """Return a shallow copy of the context replacing provided attributes."""

        return PluginContext(
            config=overrides.get("config", self.config),
            events=overrides.get("events", self.events),
            logger=overrides.get("logger", self.logger),
            scheduler=overrides.get("scheduler", self.scheduler),
            kv=overrides.get("kv", self.kv),
            secrets=overrides.get("secrets", self.secrets),
        )
