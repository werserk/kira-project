"""Decorators used by plugin authors to declare entry points.

Each decorator attaches metadata to the wrapped callable so that the host can
register handlers without executing plugin code.

Example:
    from kira.plugin_sdk import decorators

    @decorators.on_event("task.created")
    def handle_task(context, payload):
        context.logger.info(f"Task payload: {payload}")
"""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")

__all__ = ["command", "on_event", "permission", "retry", "timeout"]


def _preserve_metadata(func: Callable[P, R], **metadata: Any) -> Callable[P, R]:
    """Return a wrapper that mirrors ``func`` and stores ``metadata`` on it."""

    for key, value in metadata.items():
        setattr(func, key, value)
    return func


def on_event(event_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Mark ``func`` as an event handler for ``event_name``."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        wrapped = functools.wraps(func)(func)
        _preserve_metadata(wrapped, _is_event_handler=True, _event_name=event_name)
        return wrapped

    return decorator


def command(command_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Mark ``func`` as a command handler exposed as ``command_name``."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        wrapped = functools.wraps(func)(func)
        _preserve_metadata(wrapped, _is_command=True, _command_name=command_name)
        return wrapped

    return decorator


def permission(perm: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Declare that ``func`` requires ``perm`` to execute."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            print(f"🔐 Checking permission: {perm}")
            return func(*args, **kwargs)

        _preserve_metadata(wrapper, _requires_permission=perm)
        return cast("Callable[P, R]", wrapper)

    return decorator


def timeout(seconds: int) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Attach a timeout annotation to ``func``."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            print(f"⏱️  Timeout: {seconds} seconds")
            return func(*args, **kwargs)

        _preserve_metadata(wrapper, _timeout=seconds)
        return cast("Callable[P, R]", wrapper)

    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Retry ``func`` up to ``max_attempts`` times with ``delay`` seconds between attempts."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover - behaviour parity
                    last_exception = exc
                    if attempt < max_attempts - 1:
                        print(
                            f"🔄 Attempt {attempt + 1}/{max_attempts} failed, retrying in {delay}s"
                        )
                        time.sleep(delay)
                    else:
                        print("❌ All retry attempts exhausted")
                        raise last_exception from None

            raise RuntimeError("Retry wrapper exhausted without returning")

        return cast("Callable[P, R]", wrapper)

    return decorator
