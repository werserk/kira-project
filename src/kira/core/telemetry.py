"""Structured logging and telemetry infrastructure (ADR-015).

Provides JSONL logging with trace propagation, per-component files,
and structured fields for end-to-end traceability.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "StructuredFormatter",
    "TelemetryLogger",
    "create_logger",
    "create_span_id",
    "create_trace_id",
]


def create_trace_id() -> str:
    """Create a unique trace ID for request tracking.

    Returns
    -------
    str
        UUID-based trace ID
    """
    return str(uuid.uuid4())


def create_span_id() -> str:
    """Create a unique span ID for operation tracking.

    Returns
    -------
    str
        UUID-based span ID
    """
    return str(uuid.uuid4())[:8]  # Short span ID


class StructuredFormatter(logging.Formatter):
    """JSONL formatter for structured logging (ADR-015).

    Formats log records as JSON lines with required fields:
    - timestamp: ISO 8601 timestamp
    - level: Log level (INFO, ERROR, etc.)
    - trace_id: Request/flow identifier
    - span_id: Operation identifier
    - component: Component name (core/adapter/plugin/pipeline)
    - message: Human-readable message
    - latency_ms: Operation duration in milliseconds
    - outcome: success/failure/timeout
    - refs: Related entity IDs
    - error: Error details (type, message, stack)
    - context: Additional contextual fields
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON line.

        Parameters
        ----------
        record
            Log record to format

        Returns
        -------
        str
            JSON-formatted log line
        """
        # Base fields
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", "unknown"),
            "message": record.getMessage(),
        }

        # Trace context
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id

        if hasattr(record, "span_id"):
            log_entry["span_id"] = record.span_id

        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        # Performance metrics
        if hasattr(record, "latency_ms"):
            log_entry["latency_ms"] = record.latency_ms

        if hasattr(record, "outcome"):
            log_entry["outcome"] = record.outcome

        # References
        if hasattr(record, "refs"):
            log_entry["refs"] = record.refs

        # Context fields
        context_fields = [
            "plugin",
            "adapter",
            "pipeline",
            "event",
            "job_id",
            "entity_id",
            "chat_id",
            "task_id",
            "user_id",
        ]

        for field in context_fields:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)

        # Error details
        if record.exc_info:
            # exc_info can be True or a tuple (type, value, traceback)
            import sys

            exc_info = sys.exc_info() if record.exc_info is True else record.exc_info

            exc_type, exc_value, exc_tb = exc_info
            log_entry["error"] = {
                "type": exc_type.__name__ if exc_type else "Unknown",
                "message": str(exc_value),
                "stack": traceback.format_exception(exc_type, exc_value, exc_tb),
            }
        elif hasattr(record, "error"):
            log_entry["error"] = record.error

        return json.dumps(log_entry, ensure_ascii=False)


class TelemetryLogger:
    """Telemetry logger with structured JSONL output (ADR-015).

    Provides structured logging with trace propagation and
    per-component log files.

    Example:
        >>> logger = create_logger(component="kira-core")
        >>> logger.info("Processing started", trace_id="abc-123")
        >>> logger.error("Processing failed", error={"type": "ValueError"})
    """

    def __init__(
        self,
        *,
        component: str,
        log_dir: Path | None = None,
        level: int = logging.INFO,
        trace_id: str | None = None,
    ) -> None:
        """Initialize telemetry logger.

        Parameters
        ----------
        component
            Component name (e.g., "kira-core", "telegram-adapter")
        log_dir
            Directory for log files
        level
            Logging level
        trace_id
            Default trace ID for all logs
        """
        self.component = component
        self.trace_id = trace_id
        self.log_dir = log_dir or Path("logs")

        # Create logger
        self.logger = logging.getLogger(f"kira.{component}")
        self.logger.setLevel(level)
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers.clear()

        # Add JSONL file handler
        self._setup_file_handler()

        # Add console handler for development
        self._setup_console_handler()

    def _setup_file_handler(self) -> None:
        """Setup file handler with JSONL formatting."""
        # Determine component category
        category = self._get_category()

        # Create log directory
        log_file = self.log_dir / category / f"{self.component}.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Create file handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(StructuredFormatter())

        self.logger.addHandler(file_handler)

    def _setup_console_handler(self) -> None:
        """Setup console handler for development."""
        console_handler = logging.StreamHandler()

        # Use simple format for console
        console_format = "%(asctime)s [%(levelname)s] %(component)s: %(message)s"
        console_handler.setFormatter(logging.Formatter(console_format))

        self.logger.addHandler(console_handler)

    def _get_category(self) -> str:
        """Determine component category for log organization.

        Returns
        -------
        str
            Category name (core/adapters/plugins/pipelines)
        """
        if "adapter" in self.component.lower():
            return "adapters"
        if "plugin" in self.component.lower():
            return "plugins"
        if "pipeline" in self.component.lower():
            return "pipelines"
        return "core"

    def _log(
        self,
        level: int,
        message: str,
        *,
        trace_id: str | None = None,
        span_id: str | None = None,
        correlation_id: str | None = None,
        latency_ms: float | None = None,
        outcome: str | None = None,
        refs: list[str] | None = None,
        error: dict[str, Any] | None = None,
        **context: Any,
    ) -> None:
        """Internal logging method with structured fields.

        Parameters
        ----------
        level
            Log level
        message
            Log message
        trace_id
            Trace identifier
        span_id
            Span identifier
        correlation_id
            Correlation identifier
        latency_ms
            Operation latency in milliseconds
        outcome
            Operation outcome (success/failure/timeout)
        refs
            Related entity IDs
        error
            Error details
        **context
            Additional context fields
        """
        extra = {
            "component": self.component,
            "trace_id": trace_id or self.trace_id,
        }

        if span_id:
            extra["span_id"] = span_id

        if correlation_id:
            extra["correlation_id"] = correlation_id

        if latency_ms is not None:
            extra["latency_ms"] = latency_ms

        if outcome:
            extra["outcome"] = outcome

        if refs:
            extra["refs"] = refs

        if error:
            extra["error"] = error

        # Add context fields
        extra.update(context)

        self.logger.log(level, message, extra=extra)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message.

        Parameters
        ----------
        message
            Log message
        **kwargs
            Additional structured fields
        """
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message.

        Parameters
        ----------
        message
            Log message
        **kwargs
            Additional structured fields
        """
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message.

        Parameters
        ----------
        message
            Log message
        **kwargs
            Additional structured fields
        """
        self._log(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message.

        Parameters
        ----------
        message
            Log message
        **kwargs
            Additional structured fields
        """
        self._log(logging.DEBUG, message, **kwargs)

    def span(
        self,
        operation: str,
        *,
        trace_id: str | None = None,
        **context: Any,
    ) -> SpanContext:
        """Create a span context for operation tracing.

        Parameters
        ----------
        operation
            Operation name
        trace_id
            Trace identifier
        **context
            Additional context fields

        Returns
        -------
        SpanContext
            Span context manager
        """
        return SpanContext(
            logger=self,
            operation=operation,
            trace_id=trace_id or self.trace_id,
            context=context,
        )


class SpanContext:
    """Context manager for operation spans (ADR-015).

    Automatically tracks operation duration and outcome.

    Example:
        >>> with logger.span("process_message", entity_id="task-123"):
        ...     # Do work
        ...     pass
    """

    def __init__(
        self,
        *,
        logger: TelemetryLogger,
        operation: str,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize span context.

        Parameters
        ----------
        logger
            Parent logger
        operation
            Operation name
        trace_id
            Trace identifier
        context
            Additional context fields
        """
        self.logger = logger
        self.operation = operation
        self.trace_id = trace_id or create_trace_id()
        self.span_id = create_span_id()
        self.context = context or {}
        self.start_time = 0.0
        self.outcome = "success"

    def __enter__(self) -> SpanContext:
        """Enter span context."""
        self.start_time = time.time()

        self.logger.info(
            f"Started: {self.operation}",
            trace_id=self.trace_id,
            span_id=self.span_id,
            **self.context,
        )

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit span context."""
        latency_ms = (time.time() - self.start_time) * 1000

        if exc_type:
            self.outcome = "failure"
            self.logger.error(
                f"Failed: {self.operation}",
                trace_id=self.trace_id,
                span_id=self.span_id,
                latency_ms=latency_ms,
                outcome=self.outcome,
                error={
                    "type": exc_type.__name__,
                    "message": str(exc_val),
                },
                **self.context,
            )
        else:
            self.logger.info(
                f"Completed: {self.operation}",
                trace_id=self.trace_id,
                span_id=self.span_id,
                latency_ms=latency_ms,
                outcome=self.outcome,
                **self.context,
            )

    def set_outcome(self, outcome: str) -> None:
        """Set span outcome explicitly.

        Parameters
        ----------
        outcome
            Outcome value (success/failure/timeout)
        """
        self.outcome = outcome


def create_logger(
    *,
    component: str,
    log_dir: Path | None = None,
    level: int = logging.INFO,
    trace_id: str | None = None,
) -> TelemetryLogger:
    """Factory function to create telemetry logger.

    Parameters
    ----------
    component
        Component name
    log_dir
        Log directory
    level
        Logging level
    trace_id
        Default trace ID

    Returns
    -------
    TelemetryLogger
        Configured logger instance

    Example:
        >>> logger = create_logger(component="kira-core")
        >>> logger.info("System initialized")
    """
    return TelemetryLogger(
        component=component,
        log_dir=log_dir,
        level=level,
        trace_id=trace_id,
    )
