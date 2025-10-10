"""Loguru configuration with precise timing for performance optimization.

This module provides centralized loguru configuration with:
- High-precision timing between processes
- Structured JSON logging with correlation IDs
- Context managers for timing operations
- Decorators for automatic function timing
- Integration with existing trace_id system

Focus areas:
- NL (Telegram) -> LLM (OpenRouter, LangGraph) -> DB (Markdown, Vault)
"""

from __future__ import annotations

import functools
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = [
    "configure_loguru",
    "get_logger",
    "timing_context",
    "log_timing",
    "log_process_start",
    "log_process_end",
    "TimingLogger",
]

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable[..., Any])

# Global timing logger instance
_timing_logger: TimingLogger | None = None


def configure_loguru(
    *,
    log_dir: Path | None = None,
    level: str = "INFO",
    rotation: str = "100 MB",
    retention: str = "10 days",
    compression: str = "zip",
    enable_console: bool = True,
    enable_timing_logs: bool = True,
) -> None:
    """Configure loguru with structured logging and timing support.

    Parameters
    ----------
    log_dir
        Directory for log files (default: logs/)
    level
        Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    rotation
        Log rotation policy (e.g., "100 MB", "1 day")
    retention
        Log retention policy (e.g., "10 days", "1 week")
    compression
        Compression for rotated logs (zip, gz, bz2, xz)
    enable_console
        Enable console output
    enable_timing_logs
        Enable separate timing logs file

    Example
    -------
    >>> from kira.observability.loguru_config import configure_loguru
    >>> configure_loguru(log_dir=Path("logs"), level="INFO")
    """
    log_dir = log_dir or Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Add console handler with colored output
    if enable_console:
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>",
            level=level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    # Add main application log file (structured JSON)
    logger.add(
        log_dir / "kira.jsonl",
        format="{message}",
        level=level,
        rotation=rotation,
        retention=retention,
        compression=compression,
        serialize=True,  # JSON serialization
        backtrace=True,
        diagnose=True,
        enqueue=True,  # Async logging
    )

    # Add timing-specific log file
    if enable_timing_logs:
        logger.add(
            log_dir / "timing.jsonl",
            format="{message}",
            level="DEBUG",
            rotation=rotation,
            retention=retention,
            compression=compression,
            serialize=True,
            backtrace=False,
            diagnose=False,
            enqueue=True,
            filter=lambda record: record["extra"].get("timing", False),
        )

    # Add component-specific log files
    for component in ["telegram", "langgraph", "vault", "agent", "pipeline"]:
        logger.add(
            log_dir / f"{component}.jsonl",
            format="{message}",
            level=level,
            rotation=rotation,
            retention=retention,
            compression=compression,
            serialize=True,
            backtrace=True,
            diagnose=True,
            enqueue=True,
            filter=lambda record, comp=component: record["extra"].get("component") == comp,
        )

    logger.info("Loguru configured", log_dir=str(log_dir), level=level)


def get_logger(component: str = "kira") -> Any:
    """Get logger instance bound to specific component.

    Parameters
    ----------
    component
        Component name (telegram, langgraph, vault, agent, pipeline)

    Returns
    -------
    Logger
        Loguru logger bound to component
    """
    return logger.bind(component=component)


@contextmanager
def timing_context(
    operation: str,
    *,
    component: str = "kira",
    trace_id: str | None = None,
    **metadata: Any,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for timing operations with precise measurements.

    Parameters
    ----------
    operation
        Name of the operation being timed
    component
        Component name for filtering logs
    trace_id
        Trace ID for correlation across services
    **metadata
        Additional metadata to log

    Yields
    ------
    dict
        Context dictionary that can be updated with additional data

    Example
    -------
    >>> with timing_context("telegram_to_llm", component="agent", trace_id="abc-123") as ctx:
    ...     result = process_message(msg)
    ...     ctx["tokens"] = result.token_count
    """
    start_time = time.perf_counter()
    start_time_ns = time.perf_counter_ns()

    context: dict[str, Any] = {
        "operation": operation,
        "component": component,
        "trace_id": trace_id,
        **metadata,
    }

    # Log operation start
    logger.bind(component=component, timing=True, operation=operation, trace_id=trace_id).info(
        f"START: {operation}",
        phase="start",
        timestamp_ns=start_time_ns,
        **metadata,
    )

    try:
        yield context
    finally:
        end_time = time.perf_counter()
        end_time_ns = time.perf_counter_ns()
        duration_s = end_time - start_time
        duration_ms = duration_s * 1000
        duration_ns = end_time_ns - start_time_ns

        # Log operation end with timing
        logger.bind(component=component, timing=True, operation=operation, trace_id=trace_id).info(
            f"END: {operation}",
            phase="end",
            duration_s=duration_s,
            duration_ms=duration_ms,
            duration_ns=duration_ns,
            start_ns=start_time_ns,
            end_ns=end_time_ns,
            **{k: v for k, v in context.items() if k not in ['operation', 'component', 'trace_id']},
        )


def log_timing(component: str = "kira") -> Callable[[F], F]:
    """Decorator for automatic function timing.

    Parameters
    ----------
    component
        Component name for filtering logs

    Returns
    -------
    Callable
        Decorated function with timing

    Example
    -------
    >>> @log_timing(component="vault")
    ... def save_entity(entity):
    ...     # ... save logic ...
    ...     return entity
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract trace_id if available
            trace_id = kwargs.get("trace_id") or (
                args[0].trace_id if args and hasattr(args[0], "trace_id") else None
            )

            operation = f"{func.__module__}.{func.__name__}"

            with timing_context(operation, component=component, trace_id=trace_id):
                return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def log_process_start(
    process: str,
    *,
    component: str = "kira",
    trace_id: str | None = None,
    **metadata: Any,
) -> float:
    """Log the start of a process and return start time for manual timing.

    Parameters
    ----------
    process
        Process name
    component
        Component name
    trace_id
        Trace ID for correlation
    **metadata
        Additional metadata

    Returns
    -------
    float
        Start time (perf_counter_ns) for later calculation

    Example
    -------
    >>> start = log_process_start("telegram_message_ingestion", component="telegram", trace_id="abc")
    >>> # ... processing ...
    >>> log_process_end("telegram_message_ingestion", start, component="telegram", trace_id="abc")
    """
    start_time_ns = time.perf_counter_ns()

    logger.bind(component=component, timing=True).debug(
        f"PROCESS START: {process}",
        process=process,
        phase="start",
        trace_id=trace_id,
        timestamp_ns=start_time_ns,
        **metadata,
    )

    return start_time_ns


def log_process_end(
    process: str,
    start_time_ns: float,
    *,
    component: str = "kira",
    trace_id: str | None = None,
    **metadata: Any,
) -> float:
    """Log the end of a process with timing information.

    Parameters
    ----------
    process
        Process name
    start_time_ns
        Start time from log_process_start
    component
        Component name
    trace_id
        Trace ID for correlation
    **metadata
        Additional metadata

    Returns
    -------
    float
        Duration in milliseconds

    Example
    -------
    >>> start = log_process_start("llm_generation", component="langgraph")
    >>> # ... LLM call ...
    >>> duration = log_process_end("llm_generation", start, component="langgraph", tokens=150)
    """
    end_time_ns = time.perf_counter_ns()
    duration_ns = end_time_ns - start_time_ns
    duration_ms = duration_ns / 1_000_000
    duration_s = duration_ns / 1_000_000_000

    logger.bind(component=component, timing=True).info(
        f"PROCESS END: {process}",
        process=process,
        phase="end",
        trace_id=trace_id,
        duration_s=duration_s,
        duration_ms=duration_ms,
        duration_ns=duration_ns,
        start_ns=start_time_ns,
        end_ns=end_time_ns,
        **metadata,
    )

    return duration_ms


class TimingLogger:
    """Helper class for tracking cumulative timing across multiple operations.

    Example
    -------
    >>> timing = TimingLogger(trace_id="abc-123")
    >>> timing.start("telegram_ingestion")
    >>> # ... process ...
    >>> timing.end("telegram_ingestion", message_size=1024)
    >>> timing.start("llm_processing")
    >>> # ... LLM call ...
    >>> timing.end("llm_processing", tokens=150)
    >>> timing.log_summary()
    """

    def __init__(self, trace_id: str | None = None, component: str = "kira") -> None:
        """Initialize timing logger.

        Parameters
        ----------
        trace_id
            Trace ID for correlation
        component
            Component name
        """
        self.trace_id = trace_id
        self.component = component
        self.timings: dict[str, dict[str, Any]] = {}
        self.active_operations: dict[str, float] = {}

    def start(self, operation: str, **metadata: Any) -> None:
        """Start timing an operation.

        Parameters
        ----------
        operation
            Operation name
        **metadata
            Additional metadata
        """
        start_ns = log_process_start(
            operation,
            component=self.component,
            trace_id=self.trace_id,
            **metadata,
        )
        self.active_operations[operation] = start_ns

    def end(self, operation: str, **metadata: Any) -> float:
        """End timing an operation.

        Parameters
        ----------
        operation
            Operation name
        **metadata
            Additional metadata

        Returns
        -------
        float
            Duration in milliseconds
        """
        if operation not in self.active_operations:
            logger.warning(f"Operation {operation} was not started")
            return 0.0

        start_ns = self.active_operations.pop(operation)
        duration_ms = log_process_end(
            operation,
            start_ns,
            component=self.component,
            trace_id=self.trace_id,
            **metadata,
        )

        self.timings[operation] = {
            "duration_ms": duration_ms,
            **metadata,
        }

        return duration_ms

    def log_summary(self) -> None:
        """Log summary of all timed operations."""
        total_duration = sum(t["duration_ms"] for t in self.timings.values())

        logger.bind(component=self.component, timing=True).info(
            "TIMING SUMMARY",
            trace_id=self.trace_id,
            total_duration_ms=total_duration,
            operations=self.timings,
            num_operations=len(self.timings),
        )


def get_timing_logger(trace_id: str | None = None, component: str = "kira") -> TimingLogger:
    """Get or create timing logger instance.

    Parameters
    ----------
    trace_id
        Trace ID for correlation
    component
        Component name

    Returns
    -------
    TimingLogger
        Timing logger instance
    """
    return TimingLogger(trace_id=trace_id, component=component)

